from __future__ import annotations

from collections import OrderedDict

from plugin.mixins import DataExportMixin
from stock.models import StockItem

from .plugin_v060 import (
    AssemblyStockReconciliationPlugin as ReconciliationV060Plugin,
)
from .spillage_report import build_spillage_report


class AssemblyStockReconciliationPlugin(
    DataExportMixin,
    ReconciliationV060Plugin,
):
    """v0.6.1: native InvenTree exporter for post-assembly spillage.

    All validated reconciliation behavior and the v0.6.0 direct report action
    are retained. v0.6.1 additionally registers the plugin with InvenTree's
    Data Export framework so it appears in the Export Plugin dropdown for
    StockItem datasets, including Build Order -> Consumed Stock.
    """

    VERSION = "0.6.1"

    REPORT_HEADERS = OrderedDict(
        [
            ("build_order", "Build Order"),
            ("part_ipn", "Part / IPN"),
            ("part_name", "Part Name"),
            ("stock_items", "Stock Item(s)"),
            ("expected_quantity", "Expected Quantity"),
            ("allowed_spillage", "Allowed Spillage"),
            ("actual_consumed", "Actual Consumed"),
            ("total_over_nominal", "Total Over Nominal"),
            ("unplanned_spillage", "Unplanned Spillage"),
            ("unit_price", "Unit Price"),
            ("extended_cost", "Extended Cost"),
            ("spillage_rule", "Spillage Rule"),
            ("price_source", "Price Source"),
        ]
    )

    def supports_export(
        self,
        model_class: type,
        user,
        *args,
        **kwargs,
    ) -> bool:
        """Offer this exporter for StockItem table exports.

        The Build Order Consumed Stock table is a StockItem dataset. The
        export_data method additionally verifies that the exported queryset
        belongs to exactly one consumed Build Order before generating data.
        """
        return model_class == StockItem

    def generate_filename(self, model_class, export_format: str) -> str:
        """Generate a useful filename for the native export framework."""
        return f"post-assembly-spillage-report.{export_format}"

    def update_headers(self, headers, context, **kwargs):
        """Replace normal StockItem columns with report columns."""
        return self.REPORT_HEADERS.copy()

    @staticmethod
    def _string(value):
        if value is None:
            return ""
        return str(value)

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output,
        **kwargs,
    ):
        """Create the exception-only post-assembly spillage report.

        The native Consumed Stock export queryset is already filtered by the
        Build Order. We use that queryset only to identify the Build Order,
        then calculate the report from BuildLine consumption plus the existing
        reconciliation policy.
        """
        output.refresh_from_db()

        build_ids = list(
            queryset.exclude(consumed_by_id=None)
            .values_list("consumed_by_id", flat=True)
            .distinct()[:2]
        )

        # The report is meaningful only when the StockItem table represents
        # exactly one consumed Build Order.
        if len(build_ids) != 1:
            output.progress = queryset.count()
            output.save()

            return [
                {
                    "build_order": "",
                    "part_ipn": "REPORT NOT GENERATED",
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
                    "spillage_rule": "",
                    "price_source": "",
                }
            ]

        report = build_spillage_report(build_ids[0])

        rows = []

        for item in report["rows"]:
            rows.append(
                {
                    "build_order": report["build_reference"],
                    "part_ipn": item["ipn"] or str(item["part"]),
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
                    "spillage_rule": item["spillage_rule"],
                    "price_source": item["unit_price_source"],
                }
            )

        # Always include a final total line. If there are no exception rows,
        # this is the only line in the report.
        rows.append(
            {
                "build_order": report["build_reference"],
                "part_ipn": "TOTAL",
                "part_name": (
                    "No unplanned spillage"
                    if not report["rows"]
                    else ""
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
                "spillage_rule": "",
                "price_source": "",
            }
        )

        output.progress = queryset.count()
        output.save()

        return rows
