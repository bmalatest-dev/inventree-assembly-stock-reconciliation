# Assembly Stock Reconciliation — v0.3.0 Test Plan

This test plan separates **mechanical stock reconciliation** from **manufacturing-policy validation**.

## Core formulas

```text
actual_consumption = current_stock_quantity - physical_returned_quantity
```

For the selected Build Orders:

```text
nominal_expected_consumption
planned_spillage / overage allowance
maximum_acceptable_consumption
```

Mechanical consumption is still attributed against selected BO allocations in BO order.

## Result classes

| Condition | Expected result |
|---|---|
| Returned > current stock | BLOCK |
| Actual consumption > selected remaining allocations | BLOCK |
| Actual consumption < nominal expected consumption | HARD WARNING / investigate / explicit override |
| Actual consumption = nominal expected consumption | PASS |
| Nominal < actual consumption <= planned maximum | PASS — within planned spillage |
| Actual consumption > planned maximum but <= selected allocation | HARD WARNING / investigate / explicit override |
| Actual consumption = 0 and no nominal consumption remains | PASS / no-op |

## Phase A — regression tests

1. Single BO exact reconciliation.
2. Multi-BO consumption in BO order.
3. Insufficient selected allocation blocks.
4. Zero-consumption completed BO is a no-op.
5. Partial prior reconciliation uses only remaining allocation.
6. Native InvenTree stock splitting and Stock Tracking remain correct.
7. Repeating a completed reconciliation cannot double-consume stock.

## Phase B — nominal-return policy

### B1 — exact nominal consumption

```text
Current stock: 100
BO-0011 nominal / selected: 60
BO-0012 nominal / selected: 30
Returned: 10
Actual consumption: 90
```

Expected: PASS.

### B2 — unexpected excess return

```text
Current stock: 100
BO-0011 nominal / selected: 60
BO-0012 nominal / selected: 30
Returned: 25
Actual consumption: 75
Nominal expected: 90
```

Expected: HARD WARNING because 15 more units came back than nominally expected.

This is the first v0.3.0 UI test.

### B3 — full return while work remains

Return all current stock while selected BOs still have nominal requirement.

Expected: HARD WARNING, not a clean no-op.

## Phase C — recovered spillage / overage engine

### Footprint rules

| Case / Package | Spillage per BO |
|---|---:|
| 0201 | 200 |
| 0402 | 100 |
| 0603 | 50 |
| 0805 | 25 |
| 1206 | 20 |
| 1210 | 20 |

### Price rules when no mapped footprint applies

| Pricing max | Spillage per BO |
|---|---:|
| > 200 | 0 |
| > 50 and <= 200 | 1 |
| > 10 and <= 50 | 2 |
| <= 10 | 5 |

### Missing / zero price

- Basic passive (resistor/capacitor/inductor) + known footprint: use footprint rule.
- Basic passive + unknown footprint: 5.
- Other category: 5.

## Phase D — actual consumption within planned spillage

Use allocations which explicitly include the planned overage, because selected BO allocation remains the mechanical consumption ceiling.

Example:

```text
BO-A nominal requirement: 60
BO-A selected allocation: 65
BO-B nominal requirement: 30
BO-B selected allocation: 32

Nominal total: 90
Selected / planned max: 97
Current stock: 100
Returned: 5
Actual consumption: 95
```

Expected: PASS with policy result `within_spillage`.

Stock Tracking should state nominal expected, planned maximum, spillage rule, and actual consumption.

## Phase E — consumption beyond planned spillage

```text
Nominal expected: 90
Planned maximum: 95
Selected allocation: 100
Actual consumption: 96
```

Expected: HARD WARNING and explicit override reason.

Verify the override reason is written to Stock Tracking.

## Phase F — hard mechanical ceiling

```text
Selected allocation: 90
Actual consumption: 95
```

Expected: BLOCK. No override is permitted because InvenTree has no selected allocation against which to attribute the extra 5.

## Phase G — previous / partial reconciliations

### G1 — nominal remainder

```text
BO requirement: 75
Already consumed: 24
Remaining allocation: 51
```

Expected nominal remaining: 51.

### G2 — prior spillage usage

```text
BO nominal requirement: 75
Already consumed: 77
Planned spillage: 5
Remaining allocation: 3
```

Two units of spillage have already been used, so only three units remain in the planned allowance.

Expected:

```text
Nominal remaining: 0
Spillage remaining: 3
Planned max from remaining allocation: 3
```

## Phase H — multiple BOs with mixed allowances

Test a stock item serving at least two BOs where the allocations include different amounts of available overage.

Confirm:

- nominal requirement is aggregated correctly;
- per-BO spillage allowance is counted once per selected BO line;
- prior consumption reduces remaining nominal / spillage allowance;
- physical consumption is still attributed in BO order;
- Stock Tracking records the complete BO-order consumption breakdown.

## Phase I — data-quality / fallback tests

Verify UI display and policy behavior for:

1. known Case/Package + valid Pricing max;
2. blank Pricing max;
3. unknown Case/Package;
4. basic passive category;
5. non-passive category;
6. missing Part parameters.

## Known v0.3.0 limitation

The legacy estimating script can suppress spillage for parts listed in an external `ignore-spillage.csv`.
The live v0.3.0 plugin does **not** read that external planning CSV.

Before production deployment, decide whether those exceptions still need to be operationally enforced. If yes, they should be represented inside InvenTree (for example via a Part parameter or plugin configuration) and covered by this test plan.


## v0.3.1 JIT allocation tests

- Normal workflow: requirement 10, allocation 10, allowance 2, consumption 12 -> preview PASS; add 2 on commit.
- Extra StockItem allocation capacity unavailable -> BLOCK.
- Above planned spillage -> HARD WARNING and override; override reason and JIT allocation are recorded.
- Confirm Stock Tracking contains `JIT Allocation Added`.

## Phase K — v0.3.2 price-source tests

With blank Part Pricing and blank IC footprints:

- Stock Unit Price 10 -> spillage 5
- Stock Unit Price 25 -> spillage 2
- Stock Unit Price 75 -> spillage 1
- Stock Unit Price 250 -> spillage 0
- Blank / zero stock price -> missing-price fallback 5

Verify the UI shows the selected price source for every case.


## Phase L — v0.3.3 multi-BO exception attribution

Use the $10 active test part with BO-0013 and BO-0014 selected.

### L1 — combined planned maximum

```text
Current stock: 300
BO-0013 nominal: 10
BO-0014 nominal: 10
Spillage per BO: 5
Returned: 270
Actual consumption: 30
```

Expected:

```text
BO-0013 consume 15
BO-0014 consume 15
Exception quantity 0
```

### L2 — one unit above combined allowance

```text
Returned: 269
Actual consumption: 31
```

Expected:

```text
BO-0013 consume 16 = nominal 10 + planned spillage 5 + exception 1
BO-0014 consume 15 = nominal 10 + planned spillage 5
Planned spillage used: 10
Exception quantity: 1
HARD WARNING
```

The UI must not describe the exception unit as approved spillage.

### L3 — Stock Tracking formatting

Commit only in a disposable override test. Verify all whole-number quantities are
shown without trailing `.00000`. Verify planned JIT allocation and exception
allocation are recorded separately.

## Phase M — v0.3.4 Stock Tracking length regression

- Commit a normal multi-BO reconciliation.
- Verify each tracking note starts with `Stock Rec`.
- Verify whole-number quantities do not contain `.00000`.
- Verify each tracking note is <= 512 characters.
- In a disposable test, use a long operator note / override reason and confirm the transaction does not fail because of note length.
