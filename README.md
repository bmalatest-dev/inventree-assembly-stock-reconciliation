# v0.3.1 — Just-in-time spillage allocation

Operators continue allocating only the normal BOM requirement. If previewed physical consumption is above the existing BO allocation but within planned spillage / overage, the plugin shows the extra allocation required and creates it only on commit, inside the same transaction as native InvenTree consumption.

The review UI now shows nominal expected consumption, planned spillage / overage, maximum acceptable consumption, and additional allocation on commit. Whole-number quantities are displayed without trailing decimal zeroes.

# Assembly Stock Reconciliation — InvenTree Plugin

Version: `0.3.1` (manufacturing-policy test release)

Assembly Stock Reconciliation is an InvenTree plugin for reconciling material sent to external assembly against the quantity physically returned.

The plugin is intended for workflows where stock is allocated to one or more Build Orders, physically kitted and sent to an assembler, and the exact amount consumed is only known after unused material is returned.

## Core calculation

For each Stock Item:

`calculated consumption = current InvenTree stock quantity - physical returned quantity`

The user selects the Build Orders relevant to the assembly run. The plugin attributes consumption only against allocations belonging to those selected Build Orders.

## V1 safety rules

1. **Preview first** — `commit=false` makes no stock changes.
2. **Selected BOs define attribution** — only allocations on selected Build Orders can be consumed.
3. **Consumption cannot exceed selected allocations** — this is a blocking error.
4. **Returned quantity greater than selected allocations is a HARD WARNING when consumption is required** — commit is blocked unless `override_over_return=true` and a non-empty `override_reason` is supplied.
5. **Zero-consumption reconciliations are valid no-ops** — when `returned_quantity == current InvenTree quantity`, no remaining BO allocation is required, no allocation-based over-return warning is raised, and no stock is changed.
6. **Returned quantity greater than current InvenTree quantity is always a HARD WARNING.**
7. **Native InvenTree consumption is used** — the plugin calls `Build.complete_allocations()` so InvenTree performs its normal stock splitting, consumption, BuildLine updates, and tracking.
8. An optional `batch` can be supplied. If it does not match the Stock Item batch, processing is blocked.
9. The preview is recalculated inside a database transaction immediately before commit to reduce the risk of acting on stale stock quantities.


## 0.1.2 bug fix

- Treat `returned_quantity == current_quantity` as a successful no-op.
- Do not require a remaining BO allocation when calculated consumption is zero.
- Do not raise the allocation-based over-return warning for that zero-consumption case.
- Continue to hard-warn if the physical returned quantity exceeds the current InvenTree quantity.

## 0.3.1 manufacturing policy: nominal consumption + spillage / overage

Version 0.3.1 adds the manufacturing-policy layer recovered from the existing
estimating-allocation scripts.

### Reused spillage engine

Per-project / per-BO allowance:

| Rule | Allowance |
|---|---:|
| 0201 | 200 |
| 0402 | 100 |
| 0603 | 50 |
| 0805 | 25 |
| 1206 / 1210 | 20 |
| Price > 200 | 0 |
| Price > 50 | 1 |
| Price > 10 | 2 |
| Price <= 10 | 5 |
| Missing price, basic passive with known footprint | footprint rule |
| Missing price, other | 5 |

The plugin reads `Case/Package` from the Part parameter map and reads the cached
InvenTree `pricing_data.overall_max` value, which corresponds to the Part API / export
`pricing_max` value.

### Reconciliation policy

For the selected BOs the plugin now calculates:

```text
nominal expected consumption
planned spillage / overage allowance
maximum acceptable consumption
expected physical return range
actual calculated consumption
```

Results are classified as:

- `within_nominal`: normal.
- `within_spillage`: normal; planned spillage / overage is explicitly reported.
- `below_nominal`: HARD WARNING; more material came back than expected.
- `above_spillage_allowance`: HARD WARNING; actual consumption is beyond the planned allowance but still mechanically allocatable.
- `consumption_exceeds_allocation`: BLOCK.
- `return_exceeds_stock`: BLOCK.
- `no_op`: valid only when no nominal consumption remains.

Warnings require explicit investigation and an override reason. Blocking errors cannot be overridden.

### Automated test pathway

`tests/test_policy.py` covers the footprint and price bands plus real-world reconciliation cases:

- exact nominal consumption;
- unexpected excess return / under-consumption;
- consumption inside planned spillage;
- consumption beyond planned spillage;
- consumption beyond selected allocation;
- return greater than current stock;
- valid no-op after all nominal consumption is complete;
- invalid full return while nominal consumption remains;
- multi-BO nominal aggregation and unexpected excess return;
- multi-BO planned spillage allowance;
- partial prior reconciliation;
- prior consumption of part of the spillage allowance.

See `TEST_PLAN.md` for the staged manual manufacturing test pathway.

Run with:

```bash
python -m unittest discover -s tests -v
```

### Current limitation

The legacy estimating script also supports an optional external `ignore-spillage.csv` list.
Version 0.3.1 does not import that external CSV into the live plugin. The core footprint / price
engine is reused exactly; if the ignore-spillage exception list is still operationally required,
it should be represented in InvenTree itself (for example as a Part parameter or plugin setting)
in a follow-on release rather than depending on an external planning CSV.

## 0.2.1 reconciliation validation fix

Version 0.2.1 corrects the validation rule used by the operator UI and backend.

The plugin no longer compares the physical returned quantity directly with the
remaining Build Order allocation. That comparison is not valid after prior
partial reconciliations, because returned stock can legitimately be greater
than the remaining BO allocation.

The reconciliation rule is now:

```text
calculated_consumption = current_stock_quantity - physical_returned_quantity
```

A reconciliation is valid only when:

```text
calculated_consumption >= 0
calculated_consumption <= total remaining allocation on selected Build Orders
```

If the returned quantity exceeds the current InvenTree stock quantity, the
reconciliation is blocked for investigation.

If calculated consumption exceeds the selected remaining allocations, the
reconciliation is blocked and the operator must select additional relevant
Build Orders or investigate.

A direct `returned_quantity > selected_allocation_quantity` comparison no
longer generates a hard warning.

## 0.2.0 user interface

Version 0.2.0 adds a native Stock Item panel using InvenTree's `UserInterfaceMixin`.

From a Stock Item page, the operator can:

- See the current Stock Item, part, batch, and quantity.
- See Build Orders which still have allocations from that Stock Item.
- Select one or more relevant Build Orders.
- Enter the physical quantity returned from external assembly.
- Add optional operator notes.
- Preview the reconciliation before any stock changes occur.
- Review the deterministic BO-order consumption plan.
- Commit a normal reconciliation.
- Receive blocking validation when calculated consumption cannot be reconciled to the selected BO allocations.
- Retain the explicit override framework for future discrepancy rules which are based on independently tracked quantities sent to assembly.
- Refresh the panel after commit while InvenTree retains the native Stock Tracking audit trail.

The raw `/api/action/` interface remains available for testing and automation.

## Important V1 limitation

V1 does **not** automatically change an over-returned Stock Item to a quarantine / investigation custom status. The transaction is blocked unless expressly overridden, and the override reason is added to the consumption tracking note when consumption occurs.

Automatic quarantine / investigation handling is a candidate for a later V1.x release once the applicable custom stock status is confirmed.

## Installation

Install the plugin package into the InvenTree Python environment:

```bash
pip install -e /path/to/inventree-assembly-stock-reconciliation
```

Then restart the InvenTree server and worker so the plugin is discovered, and enable **Assembly Stock Reconciliation** in the InvenTree plugin administration interface.

## Action API

The V1 action name is:

```text
assembly_stock_reconciliation
```

### Preview

POST to:

```text
/api/action/
```

Example body:

```json
{
  "action": "assembly_stock_reconciliation",
  "data": {
    "commit": false,
    "items": [
      {
        "stock_item": 123,
        "batch": "LOT-001",
        "builds": [179, 180],
        "returned_quantity": 25
      }
    ]
  }
}
```

Example:

- Current Stock Item quantity = 100
- Physical return = 25
- Calculated consumption = 75
- Selected BO allocations total = 75 or more
- Preview returns a consumption plan showing which BuildItem allocations would be consumed.

### Commit

Repeat the request with:

```json
"commit": true
```

### Hard-warning override

If the returned amount is greater than the allocations on the selected Build Orders, the plugin returns `override_required=true` and does not commit.

After investigation, an authorized user can explicitly resubmit:

```json
{
  "action": "assembly_stock_reconciliation",
  "data": {
    "commit": true,
    "override_over_return": true,
    "override_reason": "Confirmed material from a prior kit was included in the physical return.",
    "items": [
      {
        "stock_item": 123,
        "builds": [179, 180],
        "returned_quantity": 80
      }
    ]
  }
}
```

## Suggested V1 tests

### Test A — Normal return

- Stock quantity: 100
- Selected BO allocation: 75
- Returned: 25
- Expected: consume 75; stock remaining 25.

### Test B — Partial use

- Stock quantity: 100
- Selected BO allocation: 75
- Returned: 60
- Expected: consume 40; stock remaining 60; unused allocation remains.

### Test C — Over-return

- Stock quantity: 100
- Selected BO allocation: 75
- Returned: 80
- Expected: HARD WARNING because 80 returned > 75 declared sent via selected allocations. No commit without explicit override.

### Test D — Consumption exceeds selected allocations

- Stock quantity: 100
- Selected BO allocation: 75
- Returned: 10
- Calculated consumption: 90
- Expected: BLOCK. Select another relevant Build Order / allocation or investigate.

### Test E — Wrong batch

- Stock Item batch: `LOT-001`
- Request batch: `LOT-002`
- Expected: BLOCK with batch mismatch.

## V1.1 candidates

- Search and select Build Orders by reference rather than numeric ID.
- Scan Stock Item barcode / batch.
- Automatically place hard-warning stock into an investigation / quarantine custom stock status.
- Permission gate for overrides.
- Persistent reconciliation audit table and report.
- User-selected allocation priority when multiple Build Orders share the same Stock Item.

## GitHub repository information

Recommended repository name:

```text
inventree-assembly-stock-reconciliation
```

Recommended repository description:

```text
InvenTree plugin for reconciling stock sent to external assembly against physically returned quantities and consuming the difference against selected Build Order allocations.
```

Recommended topics:

```text
inventree
inventree-plugin
inventory
manufacturing
stock-reconciliation
build-orders
external-assembly
```

Suggested release:

```text
Tag: v0.3.1
Title: Assembly Stock Reconciliation V1 UI
```

Suggested release notes:

```text
Initial test release of the Assembly Stock Reconciliation plugin.

- Preview and commit modes
- Reconciles current stock quantity against physically returned quantity
- Restricts consumption to allocations on user-selected Build Orders
- Uses InvenTree native build allocation consumption
- Blocks consumption exceeding selected allocations
- Hard-warning / explicit override workflow for over-return conditions
- Optional batch validation
- Transaction-time recalculation before commit
```

Recommended default branch: `main`

Recommended visibility: **Private** while V1 is being validated against the test InvenTree environment. It can be made public later if desired.

## Package identifiers

```text
Display name: Assembly Stock Reconciliation
Python package: inventree-assembly-stock-reconciliation
Python module: assembly_stock_reconciliation
Plugin class: AssemblyStockReconciliationPlugin
Plugin slug: assembly-stock-reconciliation
Action name: assembly_stock_reconciliation
Version: 0.3.1
```

## Stock tracking audit trail

Each committed reconciliation records a detailed InvenTree stock-tracking note including:

- Build Order responsible for the specific consumption entry
- Starting stock quantity
- Physical returned quantity
- Total reconciled consumption
- Quantity attributed to that Build Order
- Selected Build Orders and deterministic consumption order
- Optional operator notes
- Explicit override reason when an over-return override is used

Example:

```text
Assembly Stock Reconciliation | BO: BO-0008 | Starting Qty: 94.00000 | Returned Qty: 19 | Total Consumed: 75.00000 | This BO Consumed: 75.00000 | Selected BOs: BO-0008 | Consumption Order: BO-0008=75.00000
```
