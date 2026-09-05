# InvenTree Assembly Stock Reconciliation

Version **0.5.3**.

This release keeps the v0.5.2 reconciliation workflow and adds three fixes found during live validation:

- Passive identification is no longer dependent only on Part Category. Resistor / capacitor / inductor / passive identity text from the Part itself is also considered, so a $0.50+ passive receives the 20-piece-per-BO cap even when it lives in a generic category.
- Above-policy exception quantities are distributed evenly across selected Build Orders after normal spillage capacity is exhausted. Remainders are deterministic in BO order (for example, 3 across 2 BOs becomes 2 / 1).
- HARD WARNING text is policy-specific. Below-nominal cases describe the inventory reconciliation add-back; above-spillage cases describe exception allocation / consumption.

The exact-$10 price-band rule is also labeled `price_10_or_less` for clarity.
