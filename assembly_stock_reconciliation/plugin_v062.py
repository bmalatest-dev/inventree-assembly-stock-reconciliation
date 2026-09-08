from __future__ import annotations

from collections import OrderedDict

from .plugin_v061 import (
    AssemblyStockReconciliationPlugin as ReconciliationV061Plugin,
)
from .spillage_report import build_spillage_report


class AssemblyStockReconciliationPlugin(ReconciliationV061Plugin):
    """v0.6.2: supplier-facing polish for the native spillage export."""

    VERSION = "0.6.2"

    REPORT_HEADERS = OrderedDict(
        [
            ("assembly_part", "Assembly Part"),
            ("ipn", "IPN"),
            ("part_name", "Part Name"),
            ("stock_items", "Stock Item(s)"),
            ("expected_quantity", "Expected Quantity"),
            ("allowed_spillage", "Allowed Spillage"),
            ("actual_consumed", "Actual Consumed"),
            ("total_over_nominal", "Total Over Nominal"),
            ("unplanned_spillage", "Unplanned Spillage"),
            ("unit_price", "Unit Price"),
            ("extended_cost", "Extended Cost"),
        ]
    )

    def generate_filename(self, model_class, export_format: str) -> str:
        return f"post-assembly-spillage-report.{export_format}"

    def update_headers(self, headers, context, **kwargs):
        return self.REPORT_HEADERS.copy()

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output,
        **kwargs,
    ):
        """Create a supplier-facing exception-only spillage report."""
        output.refresh_from_db()

        build_ids = list(
            queryset.exclude(consumed_by_id=None)
            .values_list("consumed_by_id", flat=True)
            .distinct()[:2]
        )

        if len(build_ids) != 1:
            output.progress = queryset.count()
            output.save()

            return [
                {
                    "assembly_part": "REPORT NOT GENERATED",
                    "ipn": "",
                    "part_name": (
                        "Use this exporter from a single Build Order's "
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

        report = build_spillage_report(build_ids[0])
        rows = []

        for item in report["rows"]:
            rows.append(
                {
                    "assembly_part": report["build_part"],
                    # Supplier-facing report: leave IPN blank when none exists.
                    # Never expose the internal Part database ID as a fallback.
                    "ipn": item["ipn"] or "",
                    "part_name": item["part_name"],
                    "stock_items": ", ".join(
                        f"#{pk}" for pk in item["stock_items"]
                    ),
                    "expected_quantity": self._string(
                        item["expected_quantity"]
                    ),
                    "allowed_spillage": self._string(
                        item["allowed_spillage"]
                    ),
                    "actual_consumed": self._string(
                        item["actual_consumed"]
                    ),
                    "total_over_nominal": self._string(
                        item["total_over_nominal"]
                    ),
                    "unplanned_spillage": self._string(
                        item["unplanned_spillage"]
                    ),
                    "unit_price": self._string(item["unit_price"]),
                    "extended_cost": self._string(
                        item["extended_cost"]
                    ),
                }
            )

        rows.append(
            {
                "assembly_part": report["build_part"],
                "ipn": "",
                "part_name": (
                    "TOTAL"
                    if report["rows"]
                    else "TOTAL - No unplanned spillage"
                ),
                "stock_items": "",
                "expected_quantity": "",
                "allowed_spillage": "",
                "actual_consumed": "",
                "total_over_nominal": "",
                "unplanned_spillage": "",
                "unit_price": "",
                "extended_cost": self._string(
                    report["total_unplanned_spillage_cost"]
                ),
            }
        )

        output.progress = queryset.count()
        output.save()

        return rows
