# v0.5.1 — Fair Spillage Distribution and Readable Allocation Review

v0.5.1 builds on v0.5.0 without changing the physical-return discrepancy workflow.

## Changes

- Actual spillage / overage is now distributed as evenly as possible across the selected Build Orders instead of being assigned to the first BO.
- The distribution remains capped by each BO's individual remaining spillage allowance.
- For whole-piece quantities, odd remainders are assigned deterministically in BO order (for example 19 pieces across two BOs becomes 10 / 9).
- Any quantity beyond the combined permitted spillage remains exception quantity and uses the existing explicit-override workflow.
- Allocation Review now shows Batch ID / Batch Code as the primary Stock Item identifier when available, with the internal Stock Item number shown only as secondary context.
- Serial is used as the next fallback; Stock Item number is used only when neither Batch nor Serial is available.
- The reconciliation review table now shows the per-BO spillage / overage attribution explicitly.
- Cache-busting frontend asset: `assembly_stock_reconciliation_ui_v051.js`.

All v0.5.0 behavior remains in place: Build Part names, Part-wide Production BO allocation visibility, exact-current-stock allocation visibility, multiple-stock-item warnings, passive >= $0.50 spillage cap of 20, and below-nominal consume-plus-adjust reconciliation.
