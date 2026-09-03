# Assembly Stock Reconciliation — InvenTree Plugin

Version: `0.1.1` (V1)

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


## 0.1.1 bug fix

- Treat `returned_quantity == current_quantity` as a successful no-op.
- Do not require a remaining BO allocation when calculated consumption is zero.
- Do not raise the allocation-based over-return warning for that zero-consumption case.
- Continue to hard-warn if the physical returned quantity exceeds the current InvenTree quantity.

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

- Native UI panel / wizard instead of raw API calls.
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
Tag: v0.1.1
Title: Assembly Stock Reconciliation V1.0.1
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
Version: 0.1.1
```
