# v0.6.4 Test Plan

## Primary regression: BO-0022 with multiple discrepant parts

BO-0022 currently contains at least:
- IC-Part-75: expected 50, consumed 53
- IC-Part-25: expected 50, consumed 109

Run:

`BO-0022 -> Consumed Stock -> Download -> Export Plugin`

PASS criteria:
- Report is generated; it must NOT show `REPORT NOT GENERATED`.
- IC-Part-75 appears with its previously validated values:
  - Expected Quantity 50
  - Allowed Spillage 1
  - Actual Consumed 53
  - Total Over Nominal 3
  - Unplanned Spillage 2
  - Extended Cost 150 when unit price is 75
- IC-Part-25 also appears if its consumption exceeds nominal plus its policy
  allowance.
- Any additional discrepant BuildLine in BO-0022 also appears.
- There is no component-count or StockItem-count ceiling.
- One blank row appears after the final discrepancy line.
- TOTAL appears in Column A.
- Extended Cost on the TOTAL row equals the sum of all discrepancy rows.

## Boundary regression: BO-0023

PASS criteria:
- Export still works.
- A build with no unplanned spillage produces
  `TOTAL - No unplanned spillage` and cost 0.

## Safety check

If the exporter is launched from a generic StockItem export that truly spans
multiple Build Orders and no single Build Order can be resolved from context or
query filters, it should still refuse to generate a mixed-BO report.
