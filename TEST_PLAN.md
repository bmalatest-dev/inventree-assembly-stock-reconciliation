# v0.5.1 focused validation

## User stress case

Stock Item batch `ipn-4`, quantity 450, selected allocations:
- BO-0015 = 71
- BO-0017 = 10
- nominal total = 81

### Return 369
Expected: physical consumption 81; BO-0015 consumes 71, BO-0017 consumes 10; no JIT; no adjustment.

### Return 400
Expected: physical consumption 50; hard warning; approved commit target 81; inventory reconciliation adjustment +31; no spillage.

### Return 350
Expected: physical consumption 100; actual spillage 19. Spillage must be split evenly across the two selected BOs as 10 / 9 (deterministic BO order), not 19 / 0.
Expected plan:
- BO-0015: existing 71 + spillage/JIT 10 = consume 81
- BO-0017: existing 10 + spillage/JIT 9 = consume 19
- total consume 100

## Cap-aware distribution

For three BOs with 20 spillage allowance each and 50 actual spillage, expect 17 / 17 / 16.
For capacities 5 / 20 / 20 and 50 actual extra consumption, planned spillage is 5 / 20 / 20 and the remaining 5 is exception quantity.

## Allocation Review readability

When batches exist, rows should show entries such as:
- `ipn-1 — 10 (#19)`
- `ipn-2 — 19 (#22)`
- `ipn-4 — 71 ← current (#32)`

Stock Item numeric IDs remain secondary audit references, not the primary operator-facing identifier.
