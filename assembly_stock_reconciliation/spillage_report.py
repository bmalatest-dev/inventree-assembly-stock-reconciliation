from __future__ import annotations

import csv
from decimal import Decimal as D
from io import StringIO

from build.models import Build, BuildLine
from stock.models import StockItem

from .policy import (
    fmt_decimal,
    is_basic_passive_identity,
    normalize_footprint,
    select_effective_price,
    spillage_per_project,
)


def _money_decimal(value) -> D:
    if value is None:
        return D("0")

    amount = getattr(value, "amount", value)

    try:
        return D(str(amount))
    except Exception:
        return D("0")


def _part_category_text(part) -> str:
    category = getattr(part, "category", None)

    if not category:
        return ""

    return str(
        getattr(category, "pathstring", None)
        or getattr(category, "name", None)
        or category
    )


def _part_parameter_map(part) -> dict:
    try:
        values = part.parameters_map()
        return values if isinstance(values, dict) else {}
    except Exception:
        try:
            return {
                str(p.template.name): str(p.data)
                for p in part.parameters_list.select_related("template").all()
            }
        except Exception:
            return {}


def _case_package(part) -> str:
    params = _part_parameter_map(part)

    aliases = {
        "case/package",
        "case / package",
        "case package",
        "case-package",
        "footprint",
        "package",
        "case",
    }

    for name, value in params.items():
        if (
            str(name).strip().casefold() in aliases
            and str(value or "").strip()
        ):
            return str(value).strip()

    return ""


def _pricing_max(part) -> D:
    try:
        pricing = part.pricing_data
        return _money_decimal(getattr(pricing, "overall_max", None))
    except Exception:
        return D("0")


def _stock_unit_price(stock) -> D:
    try:
        return _money_decimal(getattr(stock, "purchase_price", None))
    except Exception:
        return D("0")


def _part_is_basic_passive(part, category_text="") -> bool:
    return is_basic_passive_identity(
        category_text,
        getattr(part, "name", ""),
        getattr(part, "IPN", ""),
        getattr(part, "description", ""),
        getattr(part, "full_name", ""),
    )


def _matching_consumed_stock(line, consumed_stock):
    """Match consumed stock to a BuildLine by its normal BOM part.

    BuildLine.consumed is authoritative for quantity. These matches are used
    for Stock Item references and price fallback only.
    """
    part = line.part
    part_id = getattr(part, "pk", None)

    return [
        stock
        for stock in consumed_stock
        if getattr(stock, "part_id", None) == part_id
    ]


def _report_unit_price(part, matching_stock):
    """Return unit price for the dollar-value report.

    Prefer Part Pricing Max. If Part Pricing is absent, use the weighted
    average purchase price of matching consumed Stock Items.
    """
    part_price = _pricing_max(part)

    if part_price > 0:
        return part_price, "part_pricing_max"

    priced = []

    for stock in matching_stock:
        price = _stock_unit_price(stock)
        qty = D(str(getattr(stock, "quantity", 0) or 0))

        if price > 0 and qty > 0:
            priced.append((price, qty))

    if priced:
        total_qty = sum((qty for _, qty in priced), D("0"))
        total_cost = sum(
            (price * qty for price, qty in priced),
            D("0"),
        )

        if total_qty > 0:
            return (
                total_cost / total_qty,
                "consumed_stock_weighted_average",
            )

    return D("0"), "missing_price_fallback"


def _policy_for_line(part, matching_stock):
    """Apply the same passive / footprint / price policy as reconciliation."""
    category = _part_category_text(part)
    case_package = _case_package(part)
    part_price = _pricing_max(part)

    stock_prices = [
        _stock_unit_price(stock)
        for stock in matching_stock
        if _stock_unit_price(stock) > 0
    ]

    stock_price = max(stock_prices, default=D("0"))

    selected = select_effective_price(part_price, stock_price)

    passive = _part_is_basic_passive(part, category)

    spill, rule = spillage_per_project(
        case_package,
        selected["effective_price"],
        category,
        passive_hint=passive,
    )

    return {
        "case_package": case_package,
        "normalized_footprint": normalize_footprint(case_package),
        "effective_price": D(str(selected["effective_price"])),
        "price_source": selected["price_source"],
        "spillage_allowance": D(str(spill)),
        "spillage_rule": rule,
    }


def build_spillage_report(build_id: int) -> dict:
    """Build an exception-only post-assembly spillage report for one BO."""
    build = Build.objects.select_related("part").get(pk=build_id)

    lines = list(
        BuildLine.objects.filter(build=build)
        .select_related(
            "bom_item",
            "bom_item__sub_part",
            "bom_item__sub_part__category",
        )
        .order_by("pk")
    )

    consumed_stock = list(
        StockItem.objects.filter(consumed_by=build)
        .select_related("part", "part__category")
        .order_by("pk")
    )

    rows = []

    for line in lines:
        part = line.part
        nominal = D(str(line.quantity))
        actual = D(str(line.consumed))
        matching_stock = _matching_consumed_stock(line, consumed_stock)

        policy = _policy_for_line(part, matching_stock)

        allowance = policy["spillage_allowance"]
        acceptable_max = nominal + allowance
        total_over_nominal = max(D("0"), actual - nominal)
        unplanned = max(D("0"), actual - acceptable_max)

        if unplanned <= 0:
            continue

        unit_price, unit_price_source = _report_unit_price(
            part,
            matching_stock,
        )

        extended_cost = unplanned * unit_price

        rows.append(
            {
                "build": build.pk,
                "build_reference": build.reference,
                "build_line": line.pk,
                "part": part.pk,
                "ipn": getattr(part, "IPN", "") or "",
                "part_name": str(
                    getattr(part, "full_name", None)
                    or getattr(part, "name", None)
                    or part
                ),
                "stock_items": [stock.pk for stock in matching_stock],
                "expected_quantity": nominal,
                "allowed_spillage": allowance,
                "acceptable_consumption_max": acceptable_max,
                "actual_consumed": actual,
                "total_over_nominal": total_over_nominal,
                "unplanned_spillage": unplanned,
                "unit_price": unit_price,
                "unit_price_source": unit_price_source,
                "extended_cost": extended_cost,
                "policy_effective_price": policy["effective_price"],
                "policy_price_source": policy["price_source"],
                "spillage_rule": policy["spillage_rule"],
            }
        )

    total_cost = sum(
        (row["extended_cost"] for row in rows),
        D("0"),
    )

    return {
        "build": build.pk,
        "build_reference": build.reference,
        "build_part": str(
            getattr(build.part, "full_name", None)
            or getattr(build.part, "name", None)
            or build.part
        ),
        "rows": rows,
        "exception_count": len(rows),
        "total_unplanned_spillage_cost": total_cost,
    }


def report_to_csv(report: dict) -> str:
    """Render the report dictionary as CSV."""
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Post Assembly Spillage Report"])
    writer.writerow(["Build Order", report["build_reference"]])
    writer.writerow(["Build Part", report["build_part"]])
    writer.writerow([])

    writer.writerow(
        [
            "Part / IPN",
            "Part Name",
            "Stock Item(s)",
            "Expected Quantity",
            "Allowed Spillage",
            "Actual Consumed",
            "Total Over Nominal",
            "Unplanned Spillage",
            "Unit Price",
            "Extended Cost",
            "Spillage Rule",
            "Price Source",
        ]
    )

    for row in report["rows"]:
        writer.writerow(
            [
                row["ipn"] or row["part"],
                row["part_name"],
                ", ".join(
                    f"#{pk}"
                    for pk in row["stock_items"]
                ),
                fmt_decimal(row["expected_quantity"]),
                fmt_decimal(row["allowed_spillage"]),
                fmt_decimal(row["actual_consumed"]),
                fmt_decimal(row["total_over_nominal"]),
                fmt_decimal(row["unplanned_spillage"]),
                fmt_decimal(row["unit_price"]),
                fmt_decimal(row["extended_cost"]),
                row["spillage_rule"],
                row["unit_price_source"],
            ]
        )

    writer.writerow([])
    writer.writerow(
        [
            "Total Unplanned Spillage Cost",
            fmt_decimal(report["total_unplanned_spillage_cost"]),
        ]
    )

    if not report["rows"]:
        writer.writerow([])
        writer.writerow(
            [
                "No consumption exceeded the nominal requirement plus "
                "the approved spillage allowance."
            ]
        )

    return output.getvalue()
