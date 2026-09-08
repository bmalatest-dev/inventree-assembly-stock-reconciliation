# InvenTree Assembly Stock Reconciliation

Version 0.6.0.

This release keeps the validated v0.5.3 reconciliation workflow unchanged and
adds a read-only **Post Assembly Spillage Report** for Build Orders.

## v0.6.0

The report identifies only component consumption which exceeds the approved
spillage policy:

```text
Unplanned Spillage =
max(Actual Consumed - Expected Consumption - Allowed Spillage, 0)
```

The report includes:

- Part / IPN
- Part name
- consumed Stock Item references
- expected quantity
- allowed spillage
- actual consumed quantity
- total quantity over nominal
- unplanned spillage
- unit price
- extended unplanned-spillage cost
- policy rule and price source
- total unplanned-spillage cost for the Build Order

The report is available as a Build Order primary action named
**Post Assembly Spillage Report** and downloads as CSV.

## Existing reconciliation policy

v0.5.3 policy behavior remains unchanged:

- Resistor / capacitor / inductor / passive identity is detected from visible
  Part identity fields as well as Part Category.
- Basic passives with an effective unit price of $0.50 or greater are capped at
  20 pieces of approved spillage per Build Order.
- Below $0.50, recognized passive footprints use their footprint allowance.
- Other components use the established price-band allowances.
- Above-policy exception quantities are distributed evenly across selected
  Build Orders after normal spillage capacity is exhausted.
- HARD WARNING text remains policy-specific for below-nominal and
  above-spillage cases.

## About

InvenTree plugin for reconciling stock sent to external assembly against
physically returned quantities and consuming the difference against selected
Build Order allocations.
