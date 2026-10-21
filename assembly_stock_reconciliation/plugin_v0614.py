from __future__ import annotations

from decimal import Decimal as D

from build.models import BuildItem
from stock.models import StockItem

from .plugin_v0613 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0613Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0613Plugin):
    """Assembly stock reconciliation v0.6.14.

    Returned material must finish the reconciliation as usable stock, not as
    stock which is still reserved against the Build Order or still flagged as
    consumed by that Build Order.

    v0.6.14 adds two post-reconciliation corrections:

    1. Release any remaining allocation on the selected Build Orders for the
       returned StockItem. A quantity which physically came back from assembly
       is no longer reserved for that assembly run.
    2. If the same StockItem was fully consumed during reconciliation and stock
       was subsequently added back by an approved reconciliation adjustment,
       clear the consumed / installed relationship so the returned quantity is
       once again considered in stock by InvenTree.

    These corrections are deliberately scoped to the Build Orders explicitly
    selected by the operator. Allocations or consumption relationships for any
    unrelated Build Order are not changed.
    """

    VERSION = "0.6.14"

    def _preview_one(self, raw, lock=False):
        """Preserve the selected Build Order IDs for commit-time cleanup.

        A line where all material is physically returned has a consumption plan
        of zero, so the selected Build Orders cannot reliably be reconstructed
        from consumption_plan alone.
        """
        preview = super()._preview_one(raw, lock=lock)

        if isinstance(preview, dict):
            build_ids = raw.get("builds") or raw.get("build_ids") or []
            preview["selected_build_ids"] = [int(pk) for pk in build_ids]

        return preview

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        """Commit reconciliation and release the physically returned stock."""
        result = super()._commit_one(
            preview=preview,
            user=user,
            notes=notes,
            override=override,
            override_reason=override_reason,
        )

        returned_qty = D(str(preview.get("returned_quantity", "0")))
        if returned_qty <= 0:
            return result

        selected_build_ids = {
            int(pk) for pk in preview.get("selected_build_ids", []) if pk is not None
        }

        if not selected_build_ids:
            return result

        stock = (
            StockItem.objects
            .select_for_update()
            .get(pk=preview["stock_item"])
        )

        # Any BuildItem quantity which remains against this StockItem represents
        # material which was *not* consumed. Since the operator has confirmed it
        # physically returned from assembly, release those selected-BO allocations
        # so InvenTree reports the material as available stock again.
        remaining_allocations = BuildItem.objects.filter(
            stock_item=stock,
            build_line__build_id__in=selected_build_ids,
        )

        released_allocation = sum(
            (D(str(qty)) for qty in remaining_allocations.values_list("quantity", flat=True)),
            D("0"),
        )

        if released_allocation > 0:
            remaining_allocations.delete()

        # InvenTree marks a StockItem as consumed by setting consumed_by when the
        # complete allocation consumes the entire StockItem. In an override case,
        # reconciliation can then add physical stock back to that same row. Merely
        # increasing quantity does not clear consumed_by, so the item remains
        # unavailable even though it has stock. Clear only relationships created by
        # one of the Build Orders explicitly selected for this reconciliation.
        fields_to_update = []

        if stock.consumed_by_id in selected_build_ids:
            stock.consumed_by = None
            fields_to_update.append("consumed_by")

            # A fully-consumed tracked component can also be attached to a build
            # output. If the operator has confirmed that quantity physically came
            # back, it is not installed in that output and must be detached.
            if stock.belongs_to_id is not None:
                stock.belongs_to = None
                fields_to_update.append("belongs_to")

        if fields_to_update:
            stock.save(update_fields=fields_to_update)

        if isinstance(result, dict):
            result["released_allocation"] = str(released_allocation)
            result["returned_stock_reactivated"] = bool(fields_to_update)

        return result
