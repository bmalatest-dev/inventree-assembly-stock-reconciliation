# InvenTree Assembly Stock Reconciliation

Version 0.6.4.

## v0.6.4 — Multi-Part Build Order Export Fix

v0.6.4 fixes Build Order resolution for the native Post Assembly Spillage
Report when a Build Order contains multiple consumed StockItems / component
parts.

The previous exporter inferred the Build Order from a limited set of
`consumed_by_id` values. That could reject a legitimate export once additional
consumed components were present.

v0.6.4 now resolves the Build Order in this order:

1. Explicit Build Order information supplied by the export context.
2. The queryset's explicit `consumed_by` filter.
3. As a fallback only, all distinct non-null `consumed_by_id` values, provided
   they resolve to exactly one Build Order.

There is no 1-part, 2-part, or StockItem count limit. After the Build Order is
identified, `build_spillage_report()` evaluates every BuildLine in the Build
Order and includes every component whose consumption exceeds nominal plus its
allowed spillage.

The supplier-facing report layout from v0.6.3 is unchanged:
- Assembly Part
- IPN
- Part Name
- Stock Item(s)
- Expected Quantity
- Allowed Spillage
- Actual Consumed
- Total Over Nominal
- Unplanned Spillage
- Unit Price
- Extended Cost

A blank separator row is retained before TOTAL when exception rows exist.
