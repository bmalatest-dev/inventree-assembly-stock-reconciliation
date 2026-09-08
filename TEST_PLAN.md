# v0.6.2 Test Plan

## 1. Export registration

After updating and restarting InvenTree:

`Build Order -> Consumed Stock -> Download -> Export Plugin`

PASS:
- Assembly Stock Reconciliation remains available as an exporter.

## 2. BO-0022 known exception

Export BO-0022.

Expected IC-Part-75 result:
- Expected Quantity: 50
- Allowed Spillage: 1
- Actual Consumed: 53
- Total Over Nominal: 3
- Unplanned Spillage: 2
- Unit Price: 75
- Extended Cost: 150

Presentation checks:
- Assembly Part shows the Part being built, not BO-0022.
- IPN is blank if IC-Part-75 has no IPN.
- Part Name shows IC-Part-75.
- No Spillage Rule column.
- No Price Source column.
- No internal Part database ID fallback.

## 3. BO-0023 boundary case

Export BO-0023.

PASS:
- No component exception rows.
- Final row says `TOTAL - No unplanned spillage`.
- Extended Cost total is 0.
- Assembly Part still identifies the Part being built.

## 4. Supplier-facing review

PASS:
- Report contains no Build Order number column.
- Report contains no policy implementation / price-source columns.
- Quantity and cost fields required to explain the discrepancy remain present.
