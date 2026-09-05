# v0.5.3 Test Plan

## Passive $0.50 priority rule
Use a resistor with footprint 0402 and effective price exactly 0.50. Expected: Planned Spillage / BO = 20 and rule `passive_price_ge_0_50_cap_20`, not footprint_0402.

For a starting quantity of 500, nominal allocation 10 and physical return 470: nominal = 10, actual spillage = 20, max acceptable consumption = 30, exception = 0.

## Multi-BO above-policy exception
Two BOs with nominal allocations 50 and 10, spillage allowance 2 each, physical consumption 67. Expected: planned spillage 2 / 2 and exception distribution 2 / 1, for total consumption 54 / 13.

## Policy-specific warning text
- below_nominal: warning must explain nominal BO consumption plus positive inventory reconciliation add-back.
- above_spillage_allowance: warning must explain consumption beyond nominal + permitted spillage and the additional exception allocation. It must not describe a higher-than-expected physical return.

## Regression
Re-run normal nominal, within-spillage, below-nominal override, allocation review, multiple-stock-item warning, return-location recommendation, and prior tracking-note tests.
