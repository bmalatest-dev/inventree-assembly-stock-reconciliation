# v0.6.0 Live Test Plan

## 1. No exception BO
Open a Build Order where every line is within nominal / approved spillage.

Expected:
- report downloads
- no exception rows
- total unplanned spillage cost = 0

## 2. Known exception
Use a Build Order with a known reconciliation exception.

Example:
- expected = 10
- allowed spillage = 20
- actual consumed = 31

Expected:
- total over nominal = 21
- unplanned spillage = 1
- extended cost = 1 x report unit price

## 3. Existing IC-Part-75 multi-BO validation
For the BO which received:
- nominal 10
- allowed spillage 1
- actual consumed 14

Expected:
- unplanned spillage = 3
- unit price = 75 when that remains the effective report price
- extended cost = 225

For the second BO:
- nominal 50
- allowed spillage 1
- actual consumed 53

Expected:
- unplanned spillage = 2
- extended cost = 150

## 4. Passive within allowance
For a $0.50+ resistor:
- expected = 10
- allowed spillage = 20
- actual = 30

Expected:
- row is NOT included

## 5. Passive above allowance
For the same resistor:
- expected = 10
- allowed spillage = 20
- actual = 31

Expected:
- unplanned spillage = 1
- row is included

## 6. Price fallback
Test a consumed stock item with no Part Pricing but a Stock Item purchase price.

Expected:
- unit price source = consumed_stock_weighted_average
- extended cost uses that price

## 7. Missing price
Test an exception line where neither Part Pricing nor consumed stock purchase
price is present.

Expected:
- exception row is still present
- unit price = 0
- extended cost = 0
- the quantity exception is not hidden simply because price is missing
