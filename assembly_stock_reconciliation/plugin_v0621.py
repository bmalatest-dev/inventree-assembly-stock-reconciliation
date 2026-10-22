from __future__ import annotations

from django.core.exceptions import ValidationError

from stock.models import StockItem
from stock.status_codes import StockStatus

from .plugin_v0620 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0620Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0620Plugin):
    """Assembly stock reconciliation v0.6.21.

    Keep the validated v0.6.20 reconciliation / consumption logic unchanged,
    while allowing the operator to set the packaging and stock status which
    should apply to material physically returned from assembly.
    """

    VERSION = "0.6.21"

    def _get_ui_context(self, stock_item_id):
        result = super()._get_ui_context(stock_item_id)

        stock = StockItem.objects.get(pk=stock_item_id)

        current_status = stock.get_custom_status()
        if current_status is None:
            current_status = stock.get_status()

        status_options = [
            {"value": int(value), "label": str(label)}
            for value, label in StockStatus.items(custom=True)
        ]

        result.update({
            "current_packaging": str(getattr(stock, "packaging", "") or ""),
            "current_status": int(current_status),
            "stock_status_options": status_options,
        })

        return result

    def _preview_one(self, raw, lock=False):
        preview = super()._preview_one(raw, lock=lock)

        # These fields are intentionally metadata only during preview. They do
        # not participate in any quantity, BO distribution, spillage, warning,
        # or allocation calculation.
        preview["return_packaging"] = str(raw.get("return_packaging", "") or "")

        return_status = raw.get("return_status")
        if return_status in (None, ""):
            preview["return_status"] = None
        else:
            try:
                preview["return_status"] = int(return_status)
            except (TypeError, ValueError):
                raise ValidationError({"return_status": "Invalid stock status."})

        return preview

    def _commit_one(
        self,
        preview,
        user,
        notes,
        override,
        override_reason,
    ):
        # First run the complete, validated v0.6.20 reconciliation unchanged.
        result = super()._commit_one(
            preview=preview,
            user=user,
            notes=notes,
            override=override,
            override_reason=override_reason,
        )

        # Packaging / status describe stock which physically returned. If no
        # quantity returned, leave both fields untouched.
        returned_qty = self._dec(preview.get("returned_quantity", "0"), "returned_quantity")
        if returned_qty <= 0:
            return result

        stock = StockItem.objects.select_for_update().get(pk=preview["stock_item"])
        changed = []

        requested_packaging = preview.get("return_packaging")
        if requested_packaging is not None:
            requested_packaging = str(requested_packaging)
            if str(getattr(stock, "packaging", "") or "") != requested_packaging:
                stock.packaging = requested_packaging
                changed.append("packaging")

        requested_status = preview.get("return_status")
        if requested_status is not None:
            if not stock.set_status(int(requested_status)):
                raise ValidationError({"return_status": "Invalid stock status."})
            changed.extend(["status", "status_custom_key"])

        if changed:
            # StockItem.set_status handles both standard and custom InvenTree
            # status codes. A normal model save preserves that mapping.
            stock.save()

        if isinstance(result, dict):
            result["return_packaging"] = str(getattr(stock, "packaging", "") or "")
            result["return_status"] = (
                stock.get_custom_status()
                if stock.get_custom_status() is not None
                else stock.get_status()
            )
            result["return_stock_details_updated"] = bool(changed)

        return result

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v0621.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
