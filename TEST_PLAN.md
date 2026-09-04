
## v0.5.2 Allocation Review presentation

1. Open Stock Item #32 / batch `ipn-4`.
2. Confirm BO-0015 renders `ipn-1`, `ipn-2`, and `ipn-4` vertically inside one Allocated Stock cell.
3. Confirm `Stock Item #19/#22/#32` appears only as smaller secondary context when batch is present.
4. Confirm the table remains exactly six columns wide.
5. With no BOs selected, confirm the current-stock warning explicitly lists BO-0013, BO-0014, BO-0015 and BO-0017 with quantities.
6. Select BO-0015 and BO-0017 and confirm that current-stock warning shrinks to BO-0013 and BO-0014 only.
7. Confirm the separate informational warning lists Production BOs that use the Part from other stock items.
8. Repeat the 450 start / 81 nominal / 350 returned preview and confirm spillage still distributes 10 / 9 across the two selected BOs.

# v0.5.2 focused validation

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
- `ipn-1 — 10` with `Stock Item #19` underneath
- `ipn-2 — 19` with `Stock Item #22` underneath
- `ipn-4 — 71 ← current` with `Stock Item #32` underneath

Stock Item numeric IDs remain secondary audit references, not the primary operator-facing identifier.
