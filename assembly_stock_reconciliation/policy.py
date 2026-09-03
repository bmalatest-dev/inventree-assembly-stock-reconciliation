from __future__ import annotations

import re
from decimal import Decimal

D = Decimal

# Recovered verbatim from the existing estimating-allocation scripts.
PASSIVE_FOOTPRINT_SPILLAGE = {
    "0201": 200,
    "0402": 100,
    "0603": 50,
    "0805": 25,
    "1206": 20,
    "1210": 20,
}


def dec(value, default="0") -> Decimal:
    try:
        if value is None or value == "":
            return D(default)
        return D(str(value))
    except Exception:
        return D(default)


def normalize_footprint(value: str) -> str:
    """Normalize package text to the footprint tokens used by the legacy engine."""
    text = str(value or "").strip().upper()
    compact = re.sub(r"[^A-Z0-9]", "", text)
    for fp in PASSIVE_FOOTPRINT_SPILLAGE:
        if fp in compact:
            return fp
    return compact


def category_is_basic_passive(part_category: str) -> bool:
    """Match the legacy definition: resistor / capacitor / inductor categories."""
    text = str(part_category or "").strip().lower()
    return any(word in text for word in ["resistor", "capacitor", "inductor"])


def spillage_per_project(case_package: str, pricing_max, part_category: str = ""):
    """Exact per-project spillage / overage rule from the estimating scripts."""
    fp = normalize_footprint(case_package)
    price = dec(pricing_max)

    if price <= 0:
        if category_is_basic_passive(part_category) and fp in PASSIVE_FOOTPRINT_SPILLAGE:
            return D(PASSIVE_FOOTPRINT_SPILLAGE[fp]), f"missing_price_passive_footprint_{fp}"
        if category_is_basic_passive(part_category):
            return D(5), "missing_price_passive_unknown_footprint_default_5"
        return D(5), "missing_price_non_passive_default_5"

    if fp in PASSIVE_FOOTPRINT_SPILLAGE:
        return D(PASSIVE_FOOTPRINT_SPILLAGE[fp]), f"footprint_{fp}"

    if price > 200:
        return D(0), "price_over_200"
    if price > 50:
        return D(1), "price_50_to_200"
    if price > 10:
        return D(2), "price_10_to_50"
    return D(5), "price_under_10_or_unknown"



def aggregate_allocation_policy(lines, spillage_per_project):
    """Aggregate nominal and acceptable consumption limits across selected BO lines.

    ``lines`` is an iterable of dictionaries containing ``allocated``, ``required`` and
    ``consumed``. Optional metadata is preserved in the returned project details.

    This pure function mirrors the live plugin logic and is intentionally Django-free so
    real-world multi-BO and prior-reconciliation behavior can be unit tested.
    """
    spill = max(D(0), dec(spillage_per_project))
    nominal_total = D(0)
    acceptable_total = D(0)
    details = []

    for raw in lines:
        allocated = max(D(0), dec(raw.get("allocated")))
        required = max(D(0), dec(raw.get("required")))
        consumed = max(D(0), dec(raw.get("consumed")))

        nominal_remaining = max(D(0), required - consumed)
        selected_nominal = min(allocated, nominal_remaining)
        already_used_spillage = max(D(0), consumed - required)
        spill_remaining = max(D(0), spill - already_used_spillage)
        selected_max = min(allocated, nominal_remaining + spill_remaining)

        nominal_total += selected_nominal
        acceptable_total += selected_max

        detail = dict(raw)
        detail.update({
            "selected_allocation": allocated,
            "line_required": required,
            "line_consumed_before": consumed,
            "nominal_remaining": nominal_remaining,
            "nominal_expected_from_selected_stock": selected_nominal,
            "spillage_allowance_per_project": spill,
            "spillage_already_used": already_used_spillage,
            "spillage_remaining": spill_remaining,
            "acceptable_consumption_max": selected_max,
        })
        details.append(detail)

    return {
        "nominal_expected_consumption": nominal_total,
        "acceptable_consumption_max": acceptable_total,
        "project_details": details,
    }


def evaluate_policy(*, current_quantity, returned_quantity, selected_allocation,
                    nominal_expected, acceptable_max):
    """Classify a reconciliation against nominal requirement and spillage policy.

    Mechanical impossibilities are blocking. Manufacturing-policy deviations are
    hard warnings which require explicit investigation / override.
    """
    current = dec(current_quantity)
    returned = dec(returned_quantity)
    allocated = dec(selected_allocation)
    nominal = max(D(0), dec(nominal_expected))
    maximum = max(nominal, dec(acceptable_max))
    consume = current - returned

    messages = []
    blocking = False
    warning = False
    classification = "normal"

    if returned < 0:
        blocking = True
        classification = "invalid_return"
        messages.append("Returned quantity cannot be negative.")
        return _result(current, returned, allocated, consume, nominal, maximum,
                       blocking, warning, classification, messages)

    if consume < 0:
        blocking = True
        classification = "return_exceeds_stock"
        messages.append(
            "Physical returned quantity exceeds the current InvenTree quantity. "
            "Investigate the stock item, prior reconciliation, or returned quantity."
        )
    elif consume > allocated:
        blocking = True
        classification = "consumption_exceeds_allocation"
        messages.append(
            f"Calculated consumption ({consume}) exceeds selected allocations ({allocated}). "
            "Select additional relevant Build Orders or investigate."
        )
    elif consume < nominal:
        warning = True
        classification = "below_nominal"
        messages.append(
            f"Calculated consumption ({consume}) is below the nominal expected consumption "
            f"({nominal}). Physical return is higher than expected; investigate before approval."
        )
    elif consume > maximum:
        warning = True
        classification = "above_spillage_allowance"
        messages.append(
            f"Calculated consumption ({consume}) exceeds the planned consumption ceiling "
            f"({maximum}), including approved spillage / overage. Investigate before approval."
        )
    elif consume > nominal:
        classification = "within_spillage"
        messages.append(
            f"Calculated consumption includes {consume - nominal} of planned spillage / overage "
            "and remains within the approved allowance."
        )
    elif consume == 0 and nominal == 0:
        classification = "no_op"
        messages.append("No consumption required; no nominal consumption remains for the selected Build Orders.")
    else:
        classification = "within_nominal"

    return _result(current, returned, allocated, consume, nominal, maximum,
                   blocking, warning, classification, messages)


def _result(current, returned, allocated, consume, nominal, maximum,
            blocking, warning, classification, messages):
    positive_consume = max(D(0), consume)
    expected_return_max = current - nominal
    expected_return_min = current - maximum
    return {
        "current_quantity": current,
        "returned_quantity": returned,
        "selected_allocation": allocated,
        "calculated_consumption": positive_consume,
        "nominal_expected_consumption": nominal,
        "acceptable_consumption_max": maximum,
        "expected_return_min": expected_return_min,
        "expected_return_max": expected_return_max,
        "blocking_error": blocking,
        "hard_warning": warning,
        "policy_classification": classification,
        "messages": messages,
    }
