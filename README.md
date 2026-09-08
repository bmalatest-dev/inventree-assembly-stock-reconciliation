# InvenTree Assembly Stock Reconciliation

Version 0.6.2.

## v0.6.2 — Supplier-Facing Spillage Report

v0.6.2 keeps the validated v0.6.1 native Consumed Stock exporter and polishes
the exported report for sharing with an external assembly house.

Changes:

- Replaces the internal Build Order column with **Assembly Part**, showing the
  Part being built.
- Separates **IPN** and **Part Name**.
- Leaves IPN blank when a component has no IPN instead of exposing the internal
  InvenTree Part database ID.
- Removes the internal **Spillage Rule** and **Price Source** columns.
- Retains only supplier-relevant quantity and cost information.
- Keeps the final total unplanned-spillage cost row.

The report columns are now:

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

The calculation remains unchanged:

```text
Acceptable Consumption = Expected Quantity + Allowed Spillage

Unplanned Spillage =
max(Actual Consumed - Expected Quantity - Allowed Spillage, 0)

Extended Cost =
Unplanned Spillage x Unit Price
```

Only component lines with unplanned spillage greater than zero are included.
A total row is always appended.

## Existing functionality

The validated reconciliation engine and v0.6.1 native InvenTree Data Export
integration remain unchanged.
