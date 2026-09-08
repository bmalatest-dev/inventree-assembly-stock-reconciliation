from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .plugin_v064 import (
    AssemblyStockReconciliationPlugin as ReconciliationV064Plugin,
)
from .spillage_report import build_spillage_report


class AssemblyStockReconciliationPlugin(ReconciliationV064Plugin):
    """v0.6.5: clean supplier-facing decimal formatting."""

    VERSION = "0.6.5"

    @staticmethod
    def _quantity(value):
        """Format quantities cleanly without unnecessary trailing zeroes."""
        if value in (None, ""):
            return ""

        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return str(value)

        if number == number.to_integral_value():
            return str(int(number))

        return format(number.normalize(), "f")

    @staticmethod
    def _money(value):
        """Format supplier-facing monetary values to exactly two decimals."""
        if value in (None, ""):
            return ""

        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return str(value)

        return f"{number:.2f}"

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output,
        **kwargs,
    ):
        """Create the finalized supplier-facing spillage report."""
        output.refresh_from_db()

        build_id = self._resolve_build_id(queryset, context)

        if build_id is None:
            output.progress = queryset.count()
            output.save()

            return [
                {
                    "assembly_part": "REPORT NOT GENERATED",
                    "ipn": "",
                    "part_name": (
                        "Could not determine a single Build Order. "
                        "Run this exporter from that Build Order's "
                        "Consumed Stock tab."
                    ),
                    "stock_items": "",
                    "expected_quantity": "",
                    "allowed_spillage": "",
                    "actual_consumed": "",
                    "total_over_nominal": "",
                    "unplanned_spillage": "",
                    "unit_price": "",
                    "extended_cost": "",
                }
            ]

        report = build_spillage_report(build_id)
        rows = []

        for item in report["rows"]:
            rows.append(
                {
                    "assembly_part": report["build_part"],
                    "ipn": item["ipn"] or "",
                    "part_name": item["part_name"],
                    "stock_items": ", ".join(
                        f"#{pk}" for pk in item["stock_items"]
                    ),
                    "expected_quantity": self._quantity(
                        item["expected_quantity"]
                    ),
                    "allowed_spillage": self._quantity(
                        item["allowed_spillage"]
                    ),
                    "actual_consumed": self._quantity(
                        item["actual_consumed"]
                    ),
                    "total_over_nominal": self._quantity(
                        item["total_over_nominal"]
                    ),
                    "unplanned_spillage": self._quantity(
                        item["unplanned_spillage"]
                    ),
                    "unit_price": self._money(item["unit_price"]),
                    "extended_cost": self._money(
                        item["extended_cost"]
                    ),
                }
            )

        if report["rows"]:
            rows.append(self._blank_row())
            total_label = "TOTAL"
        else:
            total_label = "TOTAL - No unplanned spillage"

        total_row = self._blank_row()
        total_row["assembly_part"] = total_label
        total_row["extended_cost"] = self._money(
            report["total_unplanned_spillage_cost"]
        )
        rows.append(total_row)

        output.progress = queryset.count()
        output.save()

        return rows
