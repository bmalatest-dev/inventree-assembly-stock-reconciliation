from .plugin_v0621 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0621Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0621Plugin):
    """Assembly stock reconciliation v0.6.23.

    Preserve the validated v0.6.21 reconciliation, packaging and status logic,
    while loading the corrected UI which places Returned Stock Details inside
    Section 3 with quantity and return location.
    """

    VERSION = "0.6.23"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v0623.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
