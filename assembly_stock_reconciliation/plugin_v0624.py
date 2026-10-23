from .plugin_v0621 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0621Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0621Plugin):
    """Assembly stock reconciliation v0.6.24.

    Preserve all v0.6.21 backend reconciliation / returned-stock metadata
    behavior and load a corrected UI which renders packaging and stock-status
    controls directly in Section 3.
    """

    VERSION = "0.6.24"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v0624.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
