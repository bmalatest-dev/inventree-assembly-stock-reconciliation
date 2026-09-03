from __future__ import annotations

import decimal
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction

from plugin import InvenTreePlugin
from plugin.mixins import ActionMixin

from build.models import Build, BuildItem
from stock.models import StockItem


D = decimal.Decimal


class AssemblyStockReconciliationPlugin(ActionMixin, InvenTreePlugin):
    """Reconcile stock physically returned from external assembly against selected Build Orders."""

    NAME = "AssemblyStockReconciliationPlugin"
    SLUG = "assembly-stock-reconciliation"
    TITLE = "Assembly Stock Reconciliation"
    AUTHOR = "Per Vices Corporation"
    DESCRIPTION = (
        "Reconcile returned stock against selected Build Order allocations and consume the "
        "difference using InvenTree's native build allocation consumption workflow."
    )
    VERSION = "0.1.1"
    MIN_VERSION = "1.4.0"
    LICENSE = "MIT"
    ACTION_NAME = "assembly_stock_reconciliation"

    def perform_action(self, user=None, data=None):
        data = data or {}
        self._result = self._run(user=user, data=data)

    def get_result(self, user=None, data=None):
        return getattr(self, "_result", None)

    def get_info(self, user=None, data=None):
        return {
            "action": self.ACTION_NAME,
            "version": self.VERSION,
            "modes": ["preview", "commit"],
            "summary": (
                "For each stock item: quantity_to_consume = current InvenTree quantity - "
                "physical returned quantity. Consumption is attributed only to allocations "
                "on the Build Orders selected by the user."
            ),
        }

    @staticmethod
    def _dec(value, name):
        try:
            return D(str(value))
        except (decimal.InvalidOperation, TypeError, ValueError):
            raise ValidationError({name: f"Invalid decimal value: {value!r}"})

    def _run(self, user, data):
        commit = bool(data.get("commit", False))
        override = bool(data.get("override_over_return", False))
        override_reason = str(data.get("override_reason", "")).strip()
        notes = str(data.get("notes", "")).strip()
        items = data.get("items", [])

        if not isinstance(items, list) or not items:
            raise ValidationError({"items": "Provide at least one stock item."})

        if override and not override_reason:
            raise ValidationError({
                "override_reason": "A reason is required when override_over_return is true."
            })

        previews = [self._preview_one(item) for item in items]

        hard_warnings = [p for p in previews if p["hard_warning"]]
        blocking_errors = [p for p in previews if p["blocking_error"]]

        if blocking_errors:
            return {
                "ok": False,
                "committed": False,
                "message": "One or more lines cannot be processed.",
                "items": previews,
            }

        if hard_warnings and not override:
            return {
                "ok": False,
                "committed": False,
                "override_required": True,
                "message": (
                    "Returned quantity exceeds the quantity allocated on the selected Build "
                    "Orders for at least one stock item. Investigate before approval, or resubmit "
                    "with override_over_return=true and an override_reason."
                ),
                "items": previews,
            }

        if not commit:
            return {
                "ok": True,
                "committed": False,
                "override_required": bool(hard_warnings),
                "message": "Preview only. No stock was changed.",
                "items": previews,
            }

        with transaction.atomic():
            # Recalculate under transaction before making any changes.
            previews = [self._preview_one(item, lock=True) for item in items]
            blocking_errors = [p for p in previews if p["blocking_error"]]
            hard_warnings = [p for p in previews if p["hard_warning"]]

            if blocking_errors:
                raise ValidationError("Stock changed since preview; review the returned results.")
            if hard_warnings and not override:
                raise ValidationError("Over-return condition requires explicit override.")

            for p in previews:
                self._commit_one(
                    preview=p,
                    user=user,
                    notes=notes,
                    override=override,
                    override_reason=override_reason,
                )

        return {
            "ok": True,
            "committed": True,
            "override_used": bool(hard_warnings and override),
            "message": "Returned quantities reconciled and stock consumption recorded.",
            "items": previews,
        }

    def _preview_one(self, raw, lock=False):
        if not isinstance(raw, dict):
            raise ValidationError({"items": "Each item must be an object."})

        stock_item_id = raw.get("stock_item") or raw.get("stock_item_id")
        build_ids = raw.get("builds") or raw.get("build_ids") or []
        returned = self._dec(raw.get("returned_quantity"), "returned_quantity")
        expected_batch = raw.get("batch")

        if not stock_item_id:
            raise ValidationError({"stock_item": "Stock item ID is required."})
        if not isinstance(build_ids, list) or not build_ids:
            raise ValidationError({"builds": "Select at least one relevant Build Order."})
        if returned < 0:
            raise ValidationError({"returned_quantity": "Returned quantity cannot be negative."})

        qs = StockItem.objects
        if lock:
            qs = qs.select_for_update()
        try:
            stock = qs.select_related("part").get(pk=stock_item_id)
        except StockItem.DoesNotExist:
            raise ValidationError({"stock_item": f"Stock item {stock_item_id} does not exist."})

        if expected_batch is not None and str(stock.batch or "") != str(expected_batch):
            return {
                "stock_item": stock.pk,
                "part": stock.part.full_name if hasattr(stock.part, "full_name") else str(stock.part),
                "batch": stock.batch,
                "blocking_error": True,
                "hard_warning": False,
                "messages": [
                    f"Batch mismatch: stock item batch is {stock.batch!r}, request supplied {expected_batch!r}."
                ],
            }

        builds = list(Build.objects.filter(pk__in=build_ids))
        found_ids = {b.pk for b in builds}
        missing = [bid for bid in build_ids if bid not in found_ids]

        allocations = list(
            BuildItem.objects.filter(
                stock_item=stock,
                build_line__build_id__in=build_ids,
            ).select_related("build_line", "build_line__build")
        )

        total_allocated = sum((D(str(a.quantity)) for a in allocations), D("0"))
        current_qty = D(str(stock.quantity))
        consume_qty = current_qty - returned

        messages = []
        blocking_error = False
        hard_warning = False

        if missing:
            blocking_error = True
            messages.append(f"Build Order IDs not found: {missing}")

        # A zero-consumption reconciliation is a valid no-op. This commonly occurs when
        # an operator previews / repeats a reconciliation after all required consumption
        # has already been recorded, or when the entire current stock quantity is returned.
        # In this case no remaining BO allocation is required and an allocation-based
        # over-return warning would be misleading.
        positive_consume = max(D("0"), consume_qty)

        if consume_qty < 0:
            hard_warning = True
            messages.append(
                "Physical returned quantity exceeds the current InvenTree quantity for this stock item."
            )
        elif positive_consume == 0:
            messages.append("No consumption required; returned quantity equals current stock quantity.")
        else:
            if not allocations:
                blocking_error = True
                messages.append("No allocations for this stock item exist on the selected Build Orders.")

            # The selected BO allocations are the user's declaration of what was physically sent.
            if returned > total_allocated:
                hard_warning = True
                messages.append(
                    "Physical returned quantity exceeds the quantity allocated on the selected Build Orders. "
                    "This indicates another stock item, Build Order, or prior kit may be involved."
                )

        # We cannot attribute more consumption to selected BOs than their remaining allocations.
        if positive_consume > total_allocated:
            blocking_error = True
            messages.append(
                f"Calculated consumption ({positive_consume}) exceeds selected allocations "
                f"({total_allocated}). Select additional relevant Build Orders or investigate."
            )

        plan = []
        remaining = positive_consume
        for allocation in sorted(
            allocations,
            key=lambda a: (a.build_line.build_id, a.pk),
        ):
            if remaining <= 0:
                break
            q = min(D(str(allocation.quantity)), remaining)
            if q > 0:
                plan.append({
                    "build_item": allocation.pk,
                    "build": allocation.build_line.build_id,
                    "build_reference": allocation.build_line.build.reference,
                    "allocated": str(allocation.quantity),
                    "consume": str(q),
                })
                remaining -= q

        return {
            "stock_item": stock.pk,
            "part": stock.part.full_name if hasattr(stock.part, "full_name") else str(stock.part),
            "ipn": getattr(stock.part, "IPN", None),
            "batch": stock.batch,
            "current_quantity": str(current_qty),
            "returned_quantity": str(returned),
            "selected_allocation_quantity": str(total_allocated),
            "calculated_consumption": str(positive_consume),
            "hard_warning": hard_warning,
            "blocking_error": blocking_error,
            "messages": messages,
            "consumption_plan": plan,
        }

    def _commit_one(self, preview, user, notes, override, override_reason):
        consume_qty = D(preview["calculated_consumption"])
        if consume_qty <= 0:
            # Over-return with no consumable quantity: leave stock untouched. The warning / override
            # still creates an explicit acknowledgement in the API result.
            return

        grouped = defaultdict(dict)
        for line in preview["consumption_plan"]:
            grouped[line["build"]][line["build_item"]] = D(line["consume"])

        tracking_note = "Assembly stock reconciliation"
        if notes:
            tracking_note += f" | {notes}"
        if preview["hard_warning"] and override:
            tracking_note += f" | OVERRIDE: {override_reason}"

        for build_id, quantities in grouped.items():
            build = Build.objects.select_for_update().get(pk=build_id)
            build_items = BuildItem.objects.filter(pk__in=quantities.keys())
            build.complete_allocations(
                build_items=build_items,
                quantities=quantities,
                notes=tracking_note,
                user=user,
            )
