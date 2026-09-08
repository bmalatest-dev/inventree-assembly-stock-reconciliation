# v0.6.1 Test Plan

## A. Registration / UI

1. Update the plugin through InvenTree.
2. Confirm installed package version is 0.6.1.
3. Fully restart the InvenTree Docker stack.
4. Open a Build Order.
5. Open `Consumed Stock`.
6. Click the Download / Export button.
7. Open the `Export Plugin` dropdown.

PASS:
- The Assembly Stock Reconciliation plugin is listed in addition to
  `InvenTree Exporter`.

## B. No-exception Build Order

Export a BO where all component consumption is <= expected + allowed spillage.

PASS:
- Export succeeds.
- Only a TOTAL row is present.
- Extended Cost total is 0.

## C. Known IC-Part-75 exception

Use a BO with:
- expected = 10
- allowed spillage = 1
- actual consumed = 14
- unit price = 75

PASS:
- total over nominal = 4
- unplanned spillage = 3
- extended cost = 225

For the BO with:
- expected = 50
- allowed spillage = 1
- actual consumed = 53

PASS:
- unplanned spillage = 2
- extended cost = 150

## D. Passive within allowance

$0.50+ passive:
- expected 10
- allowed 20
- actual 30

PASS:
- component row is omitted.

## E. Passive above allowance

Same passive:
- expected 10
- allowed 20
- actual 31

PASS:
- component row is included.
- unplanned spillage = 1.

## F. Wrong Stock Item context

Choose this exporter from a Stock Item table which is not scoped to exactly one
consumed Build Order.

PASS:
- Export does not crash.
- File instructs user to run the exporter from one Build Order's Consumed
  Stock tab.
