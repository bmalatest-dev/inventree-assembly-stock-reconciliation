# InvenTree Assembly Stock Reconciliation

Version 0.6.3.

## v0.6.3 — Final Total Row Presentation

This release makes a small supplier-facing presentation improvement to the
validated v0.6.2 Post Assembly Spillage Report.

When unplanned-spillage component lines are present:

1. One completely blank row is inserted after the last component line.
2. `TOTAL` is placed in Column A (`Assembly Part`).
3. The total unplanned-spillage cost remains in the final `Extended Cost`
   column.

For a report with no unplanned spillage, the report contains:

- `TOTAL - No unplanned spillage` in Column A
- `0` in the Extended Cost column

All reconciliation, spillage-policy, pricing, and exception calculations remain
unchanged from the previously validated versions.
