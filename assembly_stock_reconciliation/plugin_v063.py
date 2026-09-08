from __future__ import annotations

from .plugin_v062 import (
    AssemblyStockReconciliationPlugin as ReconciliationV062Plugin,
)
from .spillage_report import build_spillage_report


class AssemblyStockReconciliationPlugin(ReconciliationV062Plugin):
    """v0.6.3: clearer total-row presentation for supplier-facing exports."""

    VERSION = "0.6.3"

    @staticmethod
    def _blank_row():
        return {key: "" for key in AssemblyStockReconciliationPlugin.REPORT_HEADERS}

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output,
        **kwargs,
    ):
        """Create the supplier-facing exception-only spillage report."""
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

        # Supplier-facing presentation:
        # - one completely empty row before the total
        # - TOTAL label in column A
        # - total cost remains in the final Extended Cost column
        if report["rows"]:
            rows.append(self._blank_row())
            total_label = "TOTAL"
        else:
            total_label = "TOTAL - No unplanned spillage"

        total_row = self._blank_row()
        total_row["assembly_part"] = total_label
        total_row["extended_cost"] = self._string(
            report["total_unplanned_spillage_cost"]
        )
        rows.append(total_row)

        output.progress = queryset.count()
        output.save()

        return rows
