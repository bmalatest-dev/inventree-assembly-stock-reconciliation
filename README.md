# InvenTree Assembly Stock Reconciliation

Version 0.6.5.

## v0.6.5 — Final Supplier-Facing Number Formatting

This release makes the final presentation-only change to the validated
Post Assembly Spillage Report.

Changes:
- Unit Price is formatted to exactly two decimal places.
- Extended Cost is formatted to exactly two decimal places.
- TOTAL cost is formatted to exactly two decimal places.
- Quantity fields remain clean numbers without unnecessary trailing zeroes.

Examples:
- `25.000000` -> `25.00`
- `1425.00000000000` -> `1425.00`
- quantity `50.00000` -> `50`

Currency symbols are intentionally not embedded in the CSV values so the
columns remain easy to import, sort, calculate, and process in spreadsheet
software.

No reconciliation, Build Order resolution, spillage-policy, pricing-selection,
or exception calculations are changed from v0.6.4.
