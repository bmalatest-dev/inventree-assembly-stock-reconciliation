# v0.6.3 Test Plan

## BO-0022 — known exception

Export from:

`Build Order -> Consumed Stock -> Download -> Export Plugin`

Expected:
- IC-Part-75 exception remains unchanged:
  - Expected Quantity = 50
  - Allowed Spillage = 1
  - Actual Consumed = 53
  - Total Over Nominal = 3
  - Unplanned Spillage = 2
  - Unit Price = 75
  - Extended Cost = 150
- One completely blank CSV row follows the last component row.
- The next row has `TOTAL` in Column A.
- Columns B through J are blank on the TOTAL row.
- Extended Cost in Column K is 150.

## BO-0023 — no exception

Expected:
- No component exception rows.
- Column A contains `TOTAL - No unplanned spillage`.
- Extended Cost is 0.
- No unnecessary blank separator row is required because there are no
  component lines to separate from the total.

## Regression

PASS if all v0.6.2 supplier-facing columns remain unchanged and no
reconciliation or spillage calculations change.
