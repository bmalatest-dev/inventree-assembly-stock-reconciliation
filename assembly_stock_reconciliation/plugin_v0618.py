from __future__ import annotations

from .plugin_v0617 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0617Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0617Plugin):
    """Assembly stock reconciliation v0.6.18.

    Keep all v0.6.17 reconciliation behavior unchanged and refresh the
    surrounding InvenTree Stock Item page after a successful commit so the
    page-level Quantity / Available / allocation values reflect the committed
    backend state immediately.
    """

    VERSION = "0.6.18"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v0618.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
