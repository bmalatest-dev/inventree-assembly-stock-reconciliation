from __future__ import annotations

import inspect
from collections import defaultdict

from django.core.exceptions import ValidationError

from build.models import Build, BuildItem
from stock.models import StockItem, StockLocation

from .plugin_v060 import D
from .plugin_v0611 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0611Plugin,
)

class AssemblyStockReconciliationPlugin(ReconciliationV0611Plugin):
    """
    v0.6.12

    Add compatibility for both legacy and current InvenTree
    Build allocation-consumption APIs.
    """

    VERSION = "0.6.12"

    def _complete_build_allocations(
        self,
        build,
        build_items,
        quantities,
        notes,
        user,
    ):
        """
        Consume selected BuildItem allocations.

        Newer InvenTree versions provide a bulk
        Build.complete_allocations(build_items, quantities, notes, user)
        API.

        Older InvenTree versions only provide
        Build.complete_allocations(user), which consumes every allocation
        on the Build and therefore MUST NOT be used for reconciliation.

        On legacy versions, consume each selected BuildItem individually
        using BuildItem.complete_allocation(quantity, notes, user).
        """

        parameters = inspect.signature(
            Build.complete_allocations
        ).parameters

        if "build_items" in parameters:
            # Current InvenTree API
            return build.complete_allocations(
                build_items=build_items,
                quantities=quantities,
                notes=notes,
                user=user,
            )

        # Legacy InvenTree API.
        #
        # Do NOT call build.complete_allocations(user) here because the
        # legacy implementation consumes all allocations on the Build.
        for build_item in build_items:
            quantity = quantities.get(build_item.pk)

            if quantity is None:
                continue

            build_item.complete_allocation(
                quantity=quantity,
                notes=notes,
                user=user,
            )

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        """
        Commit one reconciliation.

        This is the v0.6.5 reconciliation logic with compatibility added
        for legacy InvenTree Build allocation APIs.
        """

        consume_qty = D(
            preview.get(
                "build_consumption_target",
                preview["calculated_consumption"],
            )
        )

        grouped = defaultdict(dict)

        for line in preview["consumption_plan"]:
            build_item_id = line["build_item"]

            planned_extra = D(
                str(line.get("planned_jit_allocation_required", "0"))
            )
            exception_extra = D(
                str(line.get("exception_allocation_required", "0"))
            )

            extra = planned_extra + exception_extra

            if extra > 0:
                allocation = (
                    BuildItem.objects
                    .select_for_update()
                    .get(pk=build_item_id)
                )

                allocation.quantity = (
                    D(str(allocation.quantity)) + extra
                )

                allocation.check_allocated_quantity(
                    raise_error=True
                )

                allocation.save()

            grouped[line["build"]][build_item_id] = D(
                line["consume"]
            )

        tracking_note = notes or ""

        if override and override_reason:
            if tracking_note:
                tracking_note += "\n"

            tracking_note += (
                f"Assembly reconciliation override: "
                f"{override_reason}"
            )

        for build_id, quantities in grouped.items():
            build = (
                Build.objects
                .select_for_update()
                .get(pk=build_id)
            )

            build_items = BuildItem.objects.filter(
                pk__in=quantities.keys()
            )

            self._complete_build_allocations(
                build=build,
                build_items=build_items,
                quantities=quantities,
                notes=tracking_note,
                user=user,
            )

        adjustment = D(
            str(
                preview.get(
                    "inventory_reconciliation_adjustment",
                    "0",
                )
            )
        )

        if adjustment > 0:
            stock = (
                StockItem.objects
                .select_for_update()
                .get(pk=preview["stock_item"])
            )

            adjustment_note = (
                "Assembly stock reconciliation adjustment"
            )

            if notes:
                adjustment_note += f": {notes}"

            if stock.add_stock(
                adjustment,
                user,
                notes=adjustment_note,
            ) is False:
                raise ValidationError(
                    "Failed to apply inventory "
                    "reconciliation adjustment."
                )

        returned_qty = D(
            str(preview.get("returned_quantity", "0"))
        )

        return_location_id = preview.get("return_location")

        if returned_qty > 0 and return_location_id:
            stock = (
                StockItem.objects
                .select_for_update()
                .get(pk=preview["stock_item"])
            )

            destination = StockLocation.objects.get(
                pk=return_location_id
            )

            if stock.location_id != destination.pk:
                move_note = (
                    "Assembly stock reconciliation return"
                )

                if notes:
                    move_note += f": {notes}"

                moved = stock.move(
                    destination,
                    notes=move_note,
                    user=user,
                )

                if moved is False:
                    raise ValidationError(
                        "Failed to move returned stock "
                        "to the selected location."
                    )

        return {
            "stock_item": preview["stock_item"],
            "returned_quantity": str(returned_qty),
            "consumed_quantity": str(consume_qty),
            "inventory_reconciliation_adjustment": str(
                adjustment
            ),
        }