from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D

from django.core.exceptions import ValidationError

from build.models import Build, BuildItem

from .plugin_v0614 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0614Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0614Plugin):
    """Assembly stock reconciliation v0.6.15.

    Fix just-in-time (JIT) / spillage consumption.

    The preview can legitimately plan more consumption than is currently
    allocated to the selected Build Order. Earlier versions increased the
    BuildItem allocation by the required JIT amount, but then passed only the
    *original* allocated quantity to InvenTree's consumption API. This produced
    a successful "Consumed by build order" tracking entry while leaving the JIT
    quantity allocated / available instead of consuming the full previewed
    amount.

    v0.6.15 makes the commit quantity equal the full planned consumption and
    verifies, inside the same transaction, that the selected BuildItems were
    actually reduced by that amount. A mismatch raises ValidationError so the
    outer atomic reconciliation transaction rolls back rather than leaving a
    partially reconciled stock state.
    """

    VERSION = "0.6.15"

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        """Commit one reconciliation with full JIT consumption verification."""

        # The parent v0.6.14 implementation delegates consumption to v0.6.13,
        # where JIT allocation is added but only line['consume'] is subsequently
        # consumed. Correct the preview passed to the parent so line['consume']
        # represents the complete planned amount (existing allocation + JIT /
        # exception allocation). The parent can then perform its normal locking,
        # allocation creation, stock adjustment, return handling and v0.6.14
        # returned-stock cleanup unchanged.
        commit_preview = dict(preview)
        commit_plan = []

        expected_by_build_item = defaultdict(lambda: D("0"))
        before_by_build_item = {}

        for source_line in preview.get("consumption_plan", []):
            line = dict(source_line)

            build_item_id = int(line["build_item"])
            base_consume = D(str(line.get("consume", "0")))
            planned_extra = D(str(line.get("planned_jit_allocation_required", "0")))
            exception_extra = D(str(line.get("exception_allocation_required", "0")))
            full_consume = base_consume + planned_extra + exception_extra

            line["consume"] = str(full_consume)
            commit_plan.append(line)
            expected_by_build_item[build_item_id] += full_consume

        commit_preview["consumption_plan"] = commit_plan

        # Snapshot the allocation quantities before the parent commit. This is
        # used only for post-commit verification; all writes remain in the same
        # outer reconciliation transaction.
        if expected_by_build_item:
            before_by_build_item = {
                int(pk): D(str(qty))
                for pk, qty in BuildItem.objects.filter(
                    pk__in=expected_by_build_item.keys()
                ).values_list("pk", "quantity")
            }

        result = super()._commit_one(
            preview=commit_preview,
            user=user,
            notes=notes,
            override=override,
            override_reason=override_reason,
        )

        # Verify that each planned quantity was actually consumed. The parent
        # first adds any JIT quantity to the BuildItem, then consumption reduces
        # (or deletes) that BuildItem. Therefore:
        #   expected final allocation = before + JIT/exception - full_consume
        # which simplifies to before - base_consume.
        # Checking explicitly against the plan keeps the safety rule obvious and
        # catches future API / compatibility regressions.
        failures = []

        for line in commit_plan:
            build_item_id = int(line["build_item"])
            before = before_by_build_item.get(build_item_id, D("0"))
            base_consume = D(str(preview_line_consume(preview, build_item_id)))
            expected_final = max(D("0"), before - base_consume)

            current = BuildItem.objects.filter(pk=build_item_id).values_list(
                "quantity", flat=True
            ).first()
            actual_final = D(str(current)) if current is not None else D("0")

            if actual_final != expected_final:
                failures.append(
                    f"BuildItem {build_item_id}: expected remaining allocation "
                    f"{expected_final}, found {actual_final}"
                )

        if failures:
            raise ValidationError(
                "Assembly reconciliation did not consume the full planned "
                "quantity; no changes were committed. " + "; ".join(failures)
            )

        if isinstance(result, dict):
            result["consumption_verified"] = True

        return result


def preview_line_consume(preview, build_item_id):
    """Return the original (pre-JIT) consume quantity for a BuildItem."""
    total = D("0")

    for line in preview.get("consumption_plan", []):
        if int(line["build_item"]) == int(build_item_id):
            total += D(str(line.get("consume", "0")))

    return total
