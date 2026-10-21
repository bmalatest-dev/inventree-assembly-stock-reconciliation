from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D

from django.core.exceptions import ValidationError

from build.models import BuildItem

from .plugin_v0614 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0614Plugin,
)
from .plugin_v0618 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0618Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0618Plugin):
    """Assembly stock reconciliation v0.6.19.

    Keep the v0.6.18 UI / physical-return behavior, but correct commit-time
    verification for partial physical returns.

    v0.6.15 correctly verifies ordinary consumption by expecting any
    unconsumed allocation to remain. For a physical return, however, v0.6.14
    deliberately releases that remaining selected-BO allocation after
    consumption. Therefore a successful partial-return reconciliation must end
    with zero allocation on the selected BuildItem, not with the returned
    quantity still allocated.
    """

    VERSION = "0.6.19"

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        """Commit and verify both consumed and physically returned quantities."""
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

        if expected_by_build_item:
            before_by_build_item = {
                int(pk): D(str(qty))
                for pk, qty in BuildItem.objects.filter(
                    pk__in=expected_by_build_item.keys()
                ).values_list("pk", "quantity")
            }

        # Call the v0.6.14 commit implementation directly. This preserves the
        # proven JIT/full-consumption commit path plus returned-stock cleanup,
        # while avoiding the v0.6.15 verifier whose expected-final-allocation
        # rule predates the physical-return model introduced in v0.6.16.
        result = ReconciliationV0614Plugin._commit_one(
            self,
            preview=commit_preview,
            user=user,
            notes=notes,
            override=override,
            override_reason=override_reason,
        )

        returned_qty = D(str(preview.get("returned_quantity", "0")))
        failures = []

        for line in commit_plan:
            build_item_id = int(line["build_item"])
            before = before_by_build_item.get(build_item_id, D("0"))
            base_consume = _preview_line_consume(preview, build_item_id)

            if returned_qty > 0:
                # Returned stock is deliberately released from the selected BO
                # by v0.6.14 cleanup, so no allocation should remain.
                expected_final = D("0")
            else:
                # Ordinary full-consumption / JIT behavior remains identical to
                # v0.6.15: only the amount actually consumed is removed.
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
                "Assembly reconciliation did not reach the expected final "
                "allocation state; no changes were committed. " + "; ".join(failures)
            )

        if isinstance(result, dict):
            result["consumption_verified"] = True
            result["return_release_verified"] = returned_qty > 0

        return result

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels


def _preview_line_consume(preview, build_item_id):
    total = D("0")

    for line in preview.get("consumption_plan", []):
        if int(line["build_item"]) == int(build_item_id):
            total += D(str(line.get("consume", "0")))

    return total
