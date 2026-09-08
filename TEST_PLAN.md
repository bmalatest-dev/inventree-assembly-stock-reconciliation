# v0.6.5 Test Plan

## BO-0022 final regression

Export:

`BO-0022 -> Consumed Stock -> Download -> Export Plugin`

Expected functional values remain unchanged.

IC-Part-25:
- Expected Quantity: 50
- Allowed Spillage: 2
- Actual Consumed: 109
- Unplanned Spillage: 57
- Unit Price: `25.00`
- Extended Cost: `1425.00`

IC-Part-75:
- Expected Quantity: 50
- Allowed Spillage: 1
- Actual Consumed: 53
- Unplanned Spillage: 2
- Unit Price: `75.00`
- Extended Cost: `150.00`

Final presentation:
- One blank row before TOTAL.
- TOTAL in Column A.
- Total Extended Cost: `1575.00`.
- No long decimal strings such as `25.000000` or `1425.00000000000`.

## BO-0023 boundary regression

Expected:
- No exception component rows.
- `TOTAL - No unplanned spillage` in Column A.
- Extended Cost: `0.00`.

No calculation behavior should differ from v0.6.4.
