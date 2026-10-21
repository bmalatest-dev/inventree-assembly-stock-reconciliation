from __future__ import annotations

from decimal import Decimal as D

from .plugin_v0615 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0615Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0615Plugin):
    """Assembly stock reconciliation v0.6.16.

    Treat the operator's physical return count as authoritative for stock
    consumption.

    Earlier versions treated a below-nominal physical consumption as an
    exception: they consumed the nominal Build Order quantity and then added
    the returned discrepancy back to inventory. That is incorrect when the
    StockItem already has allocations representing material sent to assembly.
    A physical return means that material was not consumed and its allocation
    should be released instead.

    Examples for a StockItem which started with quantity 2:
      * returned 0 -> consume 2
      * returned 1 -> consume 1, release the remaining allocation for 1
      * returned 2 -> consume 0, release the allocation for 2

    v0.6.14's post-commit cleanup already releases selected-BO allocations for
    returned material and moves it to the selected return location. This
    version corrects the preview / commit plan so only the physically consumed
    quantity is sent through InvenTree's Build consumption API.
    """

    VERSION = "0.6.16"

    def _preview_one(self, raw, lock=False):
        preview = super()._preview_one(raw, lock=lock)

        if not isinstance(preview, dict) or preview.get("blocking_error"):
            return preview

        returned_qty = D(str(preview.get("returned_quantity", "0")))
        physical_consumption = D(str(preview.get("calculated_consumption", "0")))
        old_build_target = D(str(preview.get("build_consumption_target", physical_consumption)))

        # The old below-nominal path consumed the nominal BO requirement and
        # restored the difference with add_stock(). Replace that plan whenever
        # physical return proves less material was actually consumed.
        if returned_qty <= 0 or physical_consumption >= old_build_target:
            return preview

        remaining = physical_consumption
        corrected_plan = []

        # Reuse the parent's deterministic BO / BuildItem ordering, but trim the
        # plan to the physical consumption quantity. No JIT or exception
        # allocation is required for material which physically came back.
        for source_line in preview.get("consumption_plan", []):
            if remaining <= 0:
                break

            line = dict(source_line)
            existing = D(str(line.get("allocated", "0")))
            consume = min(existing, remaining)

            if consume <= 0:
                continue

            line["consume"] = str(consume)
            line["planned_jit_allocation_required"] = "0"
            line["exception_allocation_required"] = "0"
            line["additional_allocation_required"] = "0"
            line["allocated_after_commit"] = str(existing)
            line["exception_consumed"] = "0"
            corrected_plan.append(line)
            remaining -= consume

        # If physical consumption cannot be represented by the existing selected
        # allocations, do not silently invent a plan. Return a blocking preview.
        if remaining > 0:
            preview["blocking_error"] = True
            preview["hard_warning"] = False
            preview.setdefault("messages", []).append(
                "Physical consumption could not be fully attributed to the existing "
                "selected Build Order allocations. Correct the allocations before commit."
            )
            return preview

        preview["consumption_plan"] = corrected_plan
        preview["build_consumption_target"] = str(physical_consumption)
        preview["inventory_reconciliation_adjustment"] = "0"
        preview["additional_allocation_required"] = "0"
        preview["planned_jit_allocation_required"] = "0"
        preview["exception_allocation_required"] = "0"
        preview["exception_consumed"] = "0"
        preview["hard_warning"] = False
        preview["policy_classification"] = "physical return reconciled"

        # The previous warning text describes the obsolete consume-then-add-back
        # behaviour. Replace it with an explanation of the physical model.
        preview["messages"] = [
            (
                f"Physical return confirms {returned_qty} remained unused. "
                f"Commit will record {physical_consumption} as consumed and release "
                "the remaining selected Build Order allocation for returned stock."
            )
        ]

        return preview
