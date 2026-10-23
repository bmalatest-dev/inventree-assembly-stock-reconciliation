from .plugin_v0621 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0621Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0621Plugin):
    """Assembly stock reconciliation v0.6.22.

    Version bump for the UI placement update which moves Returned Stock Details
    into Section 3 alongside physical quantity and return location. All
    reconciliation, packaging, and stock-status behavior remains inherited
    unchanged from v0.6.21.
    """

    VERSION = "0.6.22"
