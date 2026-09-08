# InvenTree Assembly Stock Reconciliation

Version 0.6.1.

## v0.6.1 — Native Post Assembly Spillage Export

v0.6.1 registers the plugin with InvenTree's native **Data Export** framework.

From a Build Order:

`Consumed Stock -> Download -> Export Plugin`

the Assembly Stock Reconciliation plugin is now offered as an export plugin for
the Stock Item dataset.

The resulting report contains only consumption above the acceptable ceiling:

```text
Acceptable Consumption = Expected Quantity + Allowed Spillage

Unplanned Spillage =
max(Actual Consumed - Expected Quantity - Allowed Spillage, 0)

Extended Cost =
Unplanned Spillage x Unit Price
```

A TOTAL row is appended at the bottom.

### Report columns

- Build Order
- Part / IPN
- Part Name
- Stock Item(s)
- Expected Quantity
- Allowed Spillage
- Actual Consumed
- Total Over Nominal
- Unplanned Spillage
- Unit Price
- Extended Cost
- Spillage Rule
- Price Source

### Important scope

The exporter is registered for Stock Item datasets because the Build Order
Consumed Stock table is a Stock Item table. If selected from a Stock Item export
which is not scoped to exactly one consumed Build Order, the report returns a
clear instruction to use it from a single Build Order's Consumed Stock tab.

## Existing functionality

The validated v0.5.3 reconciliation engine remains unchanged. v0.6.0's direct
Build Order report endpoint/action is also retained as a fallback while v0.6.1
adds the native export integration.

## About

InvenTree plugin for reconciling stock sent to external assembly against
physically returned quantities and reporting unplanned material spillage.
