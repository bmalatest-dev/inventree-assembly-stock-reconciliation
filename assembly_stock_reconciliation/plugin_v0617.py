from __future__ import annotations

from .plugin_v0616 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0616Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0616Plugin):
    """Assembly stock reconciliation v0.6.17.

    Keep v0.6.16 physical-return reconciliation behavior and expose the
    returned-stock action with accurate UI wording when build consumption is
    zero. A full physical return is actionable because commit releases the
    selected Build Order allocation and moves the returned stock; it is not a
    no-op.
    """

    VERSION = "0.6.17"

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v0617.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
