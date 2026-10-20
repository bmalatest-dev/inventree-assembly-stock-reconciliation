from __future__ import annotations

from django.urls import path

from .plugin_v066 import (
    AssemblyStockReconciliationPlugin as ReconciliationV066Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV066Plugin):
    """v0.6.7: production release of the plugin-owned commit endpoint."""

    VERSION = "0.6.7"

    def setup_urls(self):
        return [
            path("commit/", self.commit_reconciliation, name="commit"),
        ]

    def get_ui_panels(self, request, context, **kwargs):
        panels = super().get_ui_panels(request, context, **kwargs)

        for panel in panels:
            if panel.get("key") == "assembly-stock-reconciliation":
                panel["source"] = self.plugin_static_file(
                    "assembly_stock_reconciliation_ui_v067.js:renderPanel"
                )
                panel_context = panel.setdefault("context", {})
                panel_context["plugin_version"] = self.VERSION

        return panels
