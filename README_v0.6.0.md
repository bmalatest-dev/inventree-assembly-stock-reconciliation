# Assembly Stock Reconciliation v0.6.0 patchset

This patchset upgrades the existing v0.5.3 plugin with a **Post Assembly
Spillage Report** for Build Orders.

## What v0.6.0 adds

- Read-only report generated from the Build Order after reconciliation.
- Only shows lines where actual consumption exceeds:
  `nominal BuildLine quantity + permitted spillage`.
- Columns:
  - Part / IPN
  - Part name
  - consumed Stock Item(s)
  - expected quantity
  - allowed spillage
  - actual consumed
  - total over nominal
  - unplanned spillage
  - unit price
  - extended cost
  - spillage rule
  - price source
- Total unplanned spillage cost at the bottom.
- Reuses the existing v0.5.3 passive / footprint / price policy.
- Adds a supported Build Order **primary action**:
  `Post Assembly Spillage Report`

## Important UI note

The preferred UX discussed was:

`Build Order -> Consumed Stock -> Download -> Post Assembly Spillage Report`

As of the current InvenTree plugin UI API, plugins can add panels and primary
actions, but there is no supported hook to inject a custom item into an
individual core table's native Download menu.

For v0.6.0 this patch therefore uses the closest supported placement: a
**Post Assembly Spillage Report** primary action on the Build Order page. It
downloads the report directly as CSV.

This avoids patching InvenTree core frontend code.

## Apply

From the root of the current v0.5.3 repository:

```bash
cp /path/to/patchset/assembly_stock_reconciliation/spillage_report.py \
  assembly_stock_reconciliation/spillage_report.py

git apply /path/to/patchset/v0.6.0_UPDATE.patch
```

Then inspect:

```bash
git diff
```

Build/install using the same process used for v0.5.3.

## Report logic

For each BuildLine:

```text
Expected = BuildLine.quantity
Actual = BuildLine.consumed
Allowed Spillage = existing policy allowance

Unplanned Spillage =
max(Actual - Expected - Allowed Spillage, 0)

Extended Cost =
Unplanned Spillage x Report Unit Price
```

Only lines where `Unplanned Spillage > 0` are exported.

## Price handling

For the report dollar value:

1. Use Part Pricing Max when populated.
2. Otherwise use the weighted average purchase price of matching consumed
   Stock Items.
3. If neither is available, unit price is zero.

For selecting the spillage policy itself:

1. Use Part Pricing Max when populated.
2. Otherwise use the highest non-zero purchase price among matching consumed
   Stock Items as a conservative completed-BO policy price.
3. Otherwise use the existing missing-price fallback.

This keeps report policy selection close to the reconciliation rules while
giving a practical material-cost value for the extended loss.

## Stock Item matching

InvenTree removes BuildItem allocations as they are consumed. The permanent
BuildLine retains the actual consumed quantity, while consumed StockItems retain
`consumed_by = Build Order`.

The report therefore:
- uses `BuildLine.consumed` as the authoritative actual quantity; and
- uses the BOM item's normal stock-validity check to identify matching consumed
  Stock Item IDs for display and price calculation.

This supports normal BOM parts, allowed variants and substitutes.

## First live validation

Use a BO already validated with an exception. The report should show only the
component(s) where consumption was above the nominal + allowed ceiling and the
extended cost should equal:

`unplanned quantity x unit price`
