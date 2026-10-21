from __future__ import annotations

from collections import defaultdict
from decimal import Decimal as D

from django.core.exceptions import ValidationError

from build.models import BuildItem

from .plugin_v0614 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0614Plugin,
)
from .plugin_v0619 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0619Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0619Plugin):
    """Assembly stock reconciliation v0.6.20.

    Enforce the core physical-count invariant:

        total quantity consumed == starting quantity - physical quantity returned

    JIT / spillage / exception quantities can increase the BuildItem allocation
    available to consume, but they must never be added a second time to the
    physical consumption quantity.
    """

    VERSION = "0.6.20"

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        commit_preview = dict(preview)
        commit_plan = []

        expected_by_build_item = defaultdict(lambda: D("0"))
        before_by_build_item = {}

        # In the preview, line['consume'] already represents the amount of the
        # physically observed consumption assigned to that BuildItem. Do NOT add
        # planned_jit_allocation_required or exception_allocation_required to it.
        # The inherited v0.6.13/v0.6.14 commit code separately increases the
        # BuildItem allocation by those quantities before consuming line['consume'].
        for source_line in preview.get("consumption_plan", []):
            line = dict(source_line)
            build_item_id = int(line["build_item"])
            consume = D(str(line.get("consume", "0")))

            line["consume"] = str(consume)
            commit_plan.append(line)
            expected_by_build_item[build_item_id] += consume

        commit_preview["consumption_plan"] = commit_plan

        physical_consumption = D(str(preview.get("calculated_consumption", "0")))
        planned_consumption = sum(
            (D(str(line.get("consume", "0"))) for line in commit_plan),
            D("0"),
        )

        # Hard safety check: the transaction must never consume more or less
        # inventory than the physical count says was actually used.
        if planned_consumption != physical_consumption:
            raise ValidationError(
                "Assembly reconciliation consumption plan does not match the "
                "physical count; no changes were committed. "
                f"Physical consumption={physical_consumption}, "
                f"planned consumption={planned_consumption}."
            )

        if expected_by_build_item:
            before_by_build_item = {
                int(pk): D(str(qty))
                for pk, qty in BuildItem.objects.filter(
                    pk__in=expected_by_build_item.keys()
                ).values_list("pk", "quantity")
            }

        # v0.6.14 performs the actual transaction: it creates any required JIT /
        # exception allocation, consumes exactly line['consume'], releases returned
        # selected-BO allocation, and reactivates returned stock where required.
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
            consume = _preview_line_consume(preview, build_item_id)
            planned_extra = _preview_line_extra(preview, build_item_id)

            if returned_qty > 0:
                # Any selected-BO allocation left after consumption represents
                # physically returned material and v0.6.14 releases it.
                expected_final = D("0")
            else:
                # JIT / exception quantities extend the allocation ceiling only;
                # consumption is still exactly the physical amount assigned.
                expected_final = max(
                    D("0"),
                    before + planned_extra - consume,
                )

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
            result["physical_consumption_verified"] = str(physical_consumption)
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


def _preview_line_extra(preview, build_item_id):
    total = D("0")

    for line in preview.get("consumption_plan", []):
        if int(line["build_item"]) == int(build_item_id):
            total += D(str(line.get("planned_jit_allocation_required", "0")))
            total += D(str(line.get("exception_allocation_required", "0")))

    return total
