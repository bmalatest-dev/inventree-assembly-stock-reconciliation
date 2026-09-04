from __future__ import annotations

import decimal
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction

from plugin import InvenTreePlugin
from plugin.mixins import ActionMixin, UserInterfaceMixin

from build.models import Build, BuildItem
from stock.models import StockItem

from .policy import normalize_footprint, spillage_per_project, evaluate_policy, aggregate_allocation_policy, fmt_decimal, select_effective_price, distribute_consumption_by_policy, compact_tracking_note


D = decimal.Decimal


class AssemblyStockReconciliationPlugin(ActionMixin, UserInterfaceMixin, InvenTreePlugin):
    """Reconcile stock physically returned from external assembly against selected Build Orders."""

    NAME = "AssemblyStockReconciliationPlugin"
    SLUG = "assembly-stock-reconciliation"
    TITLE = "Assembly Stock Reconciliation"
    AUTHOR = "Per Vices Corporation"
    DESCRIPTION = (
        "Reconcile returned stock against selected Build Order allocations and consume the "
        "difference using InvenTree's native build allocation consumption workflow."
    )
    VERSION = "0.3.4"
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
        # Lightweight data endpoint used by the Stock Item UI panel.
        if data.get("ui_context"):
            return self._get_ui_context(data.get("stock_item") or data.get("stock_item_id"))

        commit = bool(data.get("commit", False))
        override = bool(data.get("override_policy_warning", data.get("override_over_return", False)))
        override_reason = str(data.get("override_reason", "")).strip()
        notes = str(data.get("notes", "")).strip()
        items = data.get("items", [])

        if not isinstance(items, list) or not items:
            raise ValidationError({"items": "Provide at least one stock item."})

        if override and not override_reason:
            raise ValidationError({
                "override_reason": "A reason is required when a reconciliation policy warning is overridden."
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
                    "One or more reconciliation lines require explicit investigation and approval. "
                    "Review the warning details, or resubmit with override_policy_warning=true and an "
                    "override_reason."
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
                raise ValidationError("Reconciliation warning requires explicit override.")

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

    def get_ui_panels(self, request, context, **kwargs):
        """Add the reconciliation workflow directly to Stock Item detail pages."""
        context = context or {}
        target_model = context.get("target_model")
        target_id = context.get("target_id")

        if target_model != "stockitem" or not target_id:
            return []

        return [{
            "key": "assembly-stock-reconciliation",
            "title": "Assembly Stock Reconciliation",
            "description": (
                "Reconcile stock returned from external assembly against selected Build Orders."
            ),
            "icon": "ti:arrows-exchange:outline",
            "source": self.plugin_static_file(
                "assembly_stock_reconciliation_ui.js:renderPanel"
            ),
            "context": {
                "stock_item_id": target_id,
                "plugin_version": self.VERSION,
            },
        }]

    @staticmethod
    def _part_category_text(part):
        category = getattr(part, "category", None)
        if not category:
            return ""
        return str(getattr(category, "pathstring", None) or getattr(category, "name", None) or category)

    @staticmethod
    def _part_parameter_map(part):
        try:
            values = part.parameters_map()
            return values if isinstance(values, dict) else {}
        except Exception:
            # Current InvenTree Part objects expose parameters_list; retain a fallback
            # so the plugin remains tolerant of older supported server versions.
            try:
                return {
                    str(p.template.name): str(p.data)
                    for p in part.parameters_list.select_related("template").all()
                }
            except Exception:
                return {}

    def _case_package(self, part):
        params = self._part_parameter_map(part)
        aliases = {
            "case/package", "case / package", "case package", "case-package",
            "footprint", "package", "case"
        }
        for name, value in params.items():
            if str(name).strip().casefold() in aliases and str(value or "").strip():
                return str(value).strip()
        return ""

    @staticmethod
    def _money_decimal(value):
        if value is None:
            return D("0")
        amount = getattr(value, "amount", value)
        try:
            return D(str(amount))
        except Exception:
            return D("0")

    def _pricing_max(self, part):
        # Prefer the cached Part Pricing maximum when it is populated.
        try:
            pricing = part.pricing_data
            return self._money_decimal(getattr(pricing, "overall_max", None))
        except Exception:
            return D("0")

    def _stock_unit_price(self, stock):
        # StockItem.purchase_price is the unit purchase price stored on the
        # physical Stock Item and is used when Part Pricing is blank / zero.
        try:
            return self._money_decimal(getattr(stock, "purchase_price", None))
        except Exception:
            return D("0")

    def _spillage_policy(self, stock):
        part = stock.part
        category = self._part_category_text(part)
        case_package = self._case_package(part)

        part_pricing_max = self._pricing_max(part)
        stock_unit_price = self._stock_unit_price(stock)
        selected = select_effective_price(part_pricing_max, stock_unit_price)

        spill, rule = spillage_per_project(
            case_package,
            selected["effective_price"],
            category,
        )

        return {
            "part_category": category,
            "case_package": case_package,
            "normalized_footprint": normalize_footprint(case_package),
            "part_pricing_max": part_pricing_max,
            "stock_unit_price": stock_unit_price,
            "effective_price": selected["effective_price"],
            "price_source": selected["price_source"],
            # Backward-compatible field name
            "pricing_max": selected["effective_price"],
            "spillage_per_project": D(str(spill)),
            "spillage_rule": rule,
        }

    @staticmethod
    def _compact_tracking_note(parts, max_length=512):
        return compact_tracking_note(parts, max_length=max_length)

    @staticmethod
    def _extra_allocation_capacity(stock):
        """Free quantity which InvenTree can still allocate from this StockItem."""
        try:
            build_allocated = D(str(stock.build_allocation_count()))
        except Exception:
            build_allocated = D("0")
        try:
            sales_allocated = D(str(stock.sales_order_allocation_count()))
        except Exception:
            sales_allocated = D("0")
        return max(D("0"), D(str(stock.quantity)) - build_allocated - sales_allocated)

    def _policy_for_allocations(self, stock, allocations):
        """Calculate nominal and spillage limits for selected allocations.

        Consumption attribution still follows deterministic BO order, while the policy
        engine evaluates the selected BOs as one physical reconciliation group.
        """
        policy = self._spillage_policy(stock)
        spill_per_project = D(str(policy["spillage_per_project"]))

        # Aggregate selected allocation by BuildLine so nominal requirement and prior
        # consumption are counted once even if more than one BuildItem references it.
        by_line = defaultdict(lambda: {
            "allocated": D("0"),
            "line": None,
            "build": None,
        })
        for allocation in allocations:
            line = allocation.build_line
            row = by_line[line.pk]
            row["allocated"] += D(str(allocation.quantity))
            row["line"] = line
            row["build"] = line.build

        rows = []
        for line_id, row in sorted(
            by_line.items(), key=lambda item: (item[1]["build"].pk, item[0])
        ):
            line = row["line"]
            build = row["build"]
            rows.append({
                "build": build.pk,
                "build_reference": build.reference,
                "build_line": line_id,
                "allocated": row["allocated"],
                "required": D(str(line.quantity)),
                "consumed": D(str(line.consumed)),
            })

        aggregate = aggregate_allocation_policy(rows, spill_per_project)
        project_details = []
        for detail in aggregate["project_details"]:
            project_details.append({
                key: (str(value) if isinstance(value, D) else value)
                for key, value in detail.items()
                if key not in {"allocated", "required", "consumed"}
            })

        return {
            **policy,
            "nominal_expected_consumption": aggregate["nominal_expected_consumption"],
            "acceptable_consumption_max": aggregate["acceptable_consumption_max"],
            "project_details": project_details,
        }

    def _get_ui_context(self, stock_item_id):
        """Return current stock and remaining Build Order allocations for the UI."""
        if not stock_item_id:
            raise ValidationError({"stock_item": "Stock item ID is required."})

        try:
            stock = StockItem.objects.select_related("part").get(pk=stock_item_id)
        except StockItem.DoesNotExist:
            raise ValidationError({
                "stock_item": f"Stock item {stock_item_id} does not exist."
            })

        allocations = list(
            BuildItem.objects.filter(
                stock_item=stock,
                quantity__gt=0,
            ).select_related("build_line", "build_line__build", "build_line__bom_item")
        )

        by_build = defaultdict(lambda: {
            "allocated": D("0"),
            "build_items": 0,
            "reference": "",
        })

        for allocation in allocations:
            build = allocation.build_line.build
            row = by_build[build.pk]
            row["allocated"] += D(str(allocation.quantity))
            row["build_items"] += 1
            row["reference"] = build.reference

        builds = [
            {
                "build": build_id,
                "reference": row["reference"],
                "allocated": str(row["allocated"]),
                "build_items": row["build_items"],
            }
            for build_id, row in sorted(by_build.items(), key=lambda item: item[0])
        ]

        part_policy = self._spillage_policy(stock)

        return {
            "ok": True,
            "ui_context": True,
            "stock_item": stock.pk,
            "part": (
                stock.part.full_name
                if hasattr(stock.part, "full_name")
                else str(stock.part)
            ),
            "ipn": getattr(stock.part, "IPN", None),
            "batch": stock.batch or "",
            "current_quantity": str(D(str(stock.quantity))),
            "builds": builds,
            "part_category": part_policy["part_category"],
            "case_package": part_policy["case_package"],
            "normalized_footprint": part_policy["normalized_footprint"],
            "part_pricing_max": str(part_policy["part_pricing_max"]),
            "stock_unit_price": str(part_policy["stock_unit_price"]),
            "effective_price": str(part_policy["effective_price"]),
            "price_source": part_policy["price_source"],
            "pricing_max": str(part_policy["pricing_max"]),
            "spillage_per_project": str(part_policy["spillage_per_project"]),
            "spillage_rule": part_policy["spillage_rule"],
            "message": (
                "Select the Build Orders which are relevant to the material returned "
                "from external assembly."
            ),
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
            ).select_related("build_line", "build_line__build", "build_line__bom_item")
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

        if not allocations and consume_qty > 0:
            blocking_error = True
            messages.append("No allocations for this stock item exist on the selected Build Orders.")

        policy = self._policy_for_allocations(stock, allocations)
        evaluation = evaluate_policy(
            current_quantity=current_qty,
            returned_quantity=returned,
            selected_allocation=total_allocated,
            nominal_expected=policy["nominal_expected_consumption"],
            acceptable_max=policy["acceptable_consumption_max"],
        )

        blocking_error = blocking_error or evaluation["blocking_error"]
        hard_warning = evaluation["hard_warning"]
        messages.extend(evaluation["messages"])
        positive_consume = evaluation["calculated_consumption"]

        additional_required = max(D("0"), positive_consume - total_allocated)
        extra_capacity = self._extra_allocation_capacity(stock)
        if additional_required > extra_capacity:
            blocking_error = True
            messages.append(
                f"Reconciliation requires {fmt_decimal(additional_required)} of additional stock allocation, "
                f"but only {fmt_decimal(extra_capacity)} is currently unallocated on this Stock Item."
            )

        allocations_by_line = defaultdict(list)
        for allocation in sorted(allocations, key=lambda a: (a.build_line.build_id, a.pk)):
            allocations_by_line[allocation.build_line_id].append(allocation)

        distribution = distribute_consumption_by_policy(
            policy["project_details"],
            positive_consume,
        )

        plan = []
        planned_jit_total = D("0")
        exception_allocation_total = D("0")
        planned_spillage_consumed_total = D("0")
        exception_consumed_total = D("0")
        unattributed = positive_consume

        for detail in distribution:
            line_id = int(detail["build_line"])
            line_allocations = allocations_by_line.get(line_id, [])
            if not line_allocations:
                continue

            existing_total = sum((D(str(a.quantity)) for a in line_allocations), D("0"))
            nominal_consumed = D(str(detail["nominal_consumed"]))
            spillage_consumed = D(str(detail["spillage_consumed"]))
            exception_consumed = D(str(detail["exception_consumed"]))
            planned_target = nominal_consumed + spillage_consumed
            total_target = planned_target + exception_consumed

            planned_jit = max(D("0"), planned_target - existing_total)
            after_planned = max(existing_total, planned_target)
            exception_jit = max(D("0"), total_target - after_planned)

            planned_jit_total += planned_jit
            exception_allocation_total += exception_jit
            planned_spillage_consumed_total += spillage_consumed
            exception_consumed_total += exception_consumed
            unattributed -= total_target

            left = total_target
            for idx, allocation in enumerate(line_allocations):
                if left <= 0:
                    break

                existing = D(str(allocation.quantity))
                amount = min(existing, left)
                add_planned = D("0")
                add_exception = D("0")

                if idx == len(line_allocations) - 1 and left > existing:
                    amount = left
                    add_planned = planned_jit
                    add_exception = exception_jit

                if amount > 0:
                    plan.append({
                        "build_item": allocation.pk,
                        "build_line": line_id,
                        "build": allocation.build_line.build_id,
                        "build_reference": allocation.build_line.build.reference,
                        "allocated": str(existing),
                        "nominal_consumed": str(nominal_consumed),
                        "planned_spillage_consumed": str(spillage_consumed),
                        "exception_consumed": str(exception_consumed),
                        "planned_jit_allocation_required": str(add_planned),
                        "exception_allocation_required": str(add_exception),
                        "additional_allocation_required": str(add_planned + add_exception),
                        "allocated_after_commit": str(existing + add_planned + add_exception),
                        "consume": str(amount),
                    })
                    left -= amount

        if unattributed > 0 and not blocking_error:
            blocking_error = True
            messages.append(
                f"Unable to attribute {fmt_decimal(unattributed)} of calculated consumption "
                "to the selected Build Orders."
            )

        if planned_jit_total > 0 and not blocking_error:
            messages.append(
                f"Commit will create {fmt_decimal(planned_jit_total)} of just-in-time Build Order "
                "allocation for planned spillage / overage."
            )

        if exception_allocation_total > 0 and hard_warning and not blocking_error:
            messages.append(
                f"Commit with override will create {fmt_decimal(exception_allocation_total)} of "
                "additional Build Order allocation to record the approved exception."
            )

        return {
            "stock_item": stock.pk,
            "part": stock.part.full_name if hasattr(stock.part, "full_name") else str(stock.part),
            "ipn": getattr(stock.part, "IPN", None),
            "batch": stock.batch,
            "current_quantity": str(current_qty),
            "returned_quantity": str(returned),
            "selected_allocation_quantity": str(total_allocated),
            "calculated_consumption": str(positive_consume),
            "nominal_expected_consumption": str(policy["nominal_expected_consumption"]),
            "planned_spillage_per_project": str(policy["spillage_per_project"]),
            "planned_spillage_allowance": str(max(D("0"), policy["acceptable_consumption_max"] - policy["nominal_expected_consumption"])),
            "acceptable_consumption_max": str(policy["acceptable_consumption_max"]),
            "additional_allocation_required": str(additional_required),
            "planned_jit_allocation_required": str(planned_jit_total),
            "exception_allocation_required": str(exception_allocation_total),
            "planned_spillage_consumed": str(planned_spillage_consumed_total),
            "exception_consumed": str(exception_consumed_total),
            "extra_allocation_capacity": str(extra_capacity),
            "expected_return_min": str(evaluation["expected_return_min"]),
            "expected_return_max": str(evaluation["expected_return_max"]),
            "policy_classification": evaluation["policy_classification"],
            "spillage_rule": policy["spillage_rule"],
            "part_category": policy["part_category"],
            "case_package": policy["case_package"],
            "normalized_footprint": policy["normalized_footprint"],
            "part_pricing_max": str(policy["part_pricing_max"]),
            "stock_unit_price": str(policy["stock_unit_price"]),
            "effective_price": str(policy["effective_price"]),
            "price_source": policy["price_source"],
            "pricing_max": str(policy["pricing_max"]),
            "policy_projects": policy["project_details"],
            "hard_warning": hard_warning,
            "blocking_error": blocking_error,
            "messages": messages,
            "consumption_plan": plan,
        }

    def _commit_one(self, preview, user, notes, override, override_reason):
        consume_qty = D(preview["calculated_consumption"])
        if consume_qty <= 0:
            # No physical consumption is required, so leave stock untouched. Any policy
            # warning / override remains explicit in the API result.
            return

        grouped = defaultdict(dict)
        for line in preview["consumption_plan"]:
            build_item_id = line["build_item"]
            planned_extra = D(str(line.get("planned_jit_allocation_required", "0")))
            exception_extra = D(str(line.get("exception_allocation_required", "0")))
            extra = planned_extra + exception_extra
            if extra > 0:
                allocation = BuildItem.objects.select_for_update().get(pk=build_item_id)
                allocation.quantity = D(str(allocation.quantity)) + extra
                allocation.check_allocated_quantity(raise_error=True)
                allocation.save()
            grouped[line["build"]][build_item_id] = D(line["consume"])

        # Build a detailed audit note for each stock-tracking entry. Each call to
        # complete_allocations() is scoped to one Build Order, so record both the
        # overall reconciliation and the amount attributed to that specific BO.
        selected_bos = ", ".join(dict.fromkeys(
            line["build_reference"] for line in preview["consumption_plan"]
        ))
        allocation_breakdown = ", ".join(
            f'{line["build_reference"]}={fmt_decimal(line["consume"])}'
            for line in preview["consumption_plan"]
        )

        for build_id, quantities in grouped.items():
            build = Build.objects.select_for_update().get(pk=build_id)
            build_items = BuildItem.objects.filter(pk__in=quantities.keys())
            this_build_consumption = sum(quantities.values(), D("0"))

            this_build_planned_jit = sum((
                D(str(x.get("planned_jit_allocation_required", "0")))
                for x in preview["consumption_plan"] if x["build"] == build_id
            ), D("0"))
            this_build_exception_allocation = sum((
                D(str(x.get("exception_allocation_required", "0")))
                for x in preview["consumption_plan"] if x["build"] == build_id
            ), D("0"))
            this_build_spillage_consumed = sum((
                D(str(x.get("planned_spillage_consumed", "0")))
                for x in preview["consumption_plan"] if x["build"] == build_id
            ), D("0"))
            this_build_exception_consumed = sum((
                D(str(x.get("exception_consumed", "0")))
                for x in preview["consumption_plan"] if x["build"] == build_id
            ), D("0"))

            tracking_parts = [
                "Stock Rec",
                f"BO {build.reference}",
                f"Start {fmt_decimal(preview['current_quantity'])}",
                f"Return {fmt_decimal(preview['returned_quantity'])}",
                f"Consumed {fmt_decimal(this_build_consumption)}",
                f"Nominal {fmt_decimal(preview.get('nominal_expected_consumption', '0'))}",
                f"SpillAllow {fmt_decimal(preview.get('planned_spillage_allowance', '0'))}",
                f"SpillUsed {fmt_decimal(this_build_spillage_consumed)}",
                f"Exception {fmt_decimal(this_build_exception_consumed)}",
                f"JIT {fmt_decimal(this_build_planned_jit)}",
                f"ExAlloc {fmt_decimal(this_build_exception_allocation)}",
                f"Policy {preview.get('policy_classification', '')}",
                f"Rule {preview.get('spillage_rule', '')}",
                f"Price {fmt_decimal(preview.get('effective_price', '0'))}",
                f"Src {preview.get('price_source', '')}",
                f"Selected {selected_bos}",
                f"Order {allocation_breakdown}",
            ]

            if notes:
                tracking_parts.append(f"Notes {notes}")
            if preview["hard_warning"] and override:
                tracking_parts.append(f"OVERRIDE {override_reason}")

            tracking_note = self._compact_tracking_note(tracking_parts, max_length=512)

            build.complete_allocations(
                build_items=build_items,
                quantities=quantities,
                notes=tracking_note,
                user=user,
            )
