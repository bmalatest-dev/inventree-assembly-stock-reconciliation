from __future__ import annotations

from .plugin_v063 import (
    AssemblyStockReconciliationPlugin as ReconciliationV063Plugin,
)
from .spillage_report import build_spillage_report


class AssemblyStockReconciliationPlugin(ReconciliationV063Plugin):
    """v0.6.4: robust single-Build-Order resolution for consumed-stock exports."""

    VERSION = "0.6.4"

    @staticmethod
    def _coerce_pk(value):
        """Return an integer primary key where possible."""
        if value is None:
            return None

        if hasattr(value, "pk"):
            value = value.pk

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _build_id_from_context(cls, context):
        """Best-effort resolution of the Build Order from exporter context.

        InvenTree export context can vary by view/version. We therefore only
        accept build-specific keys / objects and never treat an arbitrary `pk`
        as a Build ID.
        """
        if not isinstance(context, dict):
            return None

        direct_keys = (
            "build_id",
            "build_pk",
            "build_order_id",
            "build_order_pk",
        )

        for key in direct_keys:
            if key in context:
                pk = cls._coerce_pk(context.get(key))
                if pk is not None:
                    return pk

        object_keys = (
            "build",
            "build_order",
        )

        for key in object_keys:
            if key in context:
                pk = cls._coerce_pk(context.get(key))
                if pk is not None:
                    return pk

        # Some export contexts nest view / request / table context.
        # Recurse only into dictionaries, looking for the explicit keys above.
        for value in context.values():
            if isinstance(value, dict):
                pk = cls._build_id_from_context(value)
                if pk is not None:
                    return pk

        return None

    @classmethod
    def _build_id_from_queryset_filter(cls, queryset):
        """Inspect the queryset WHERE tree for an explicit consumed_by filter.

        This is preferable to looking at the rows themselves because a Build
        Order's Consumed Stock table may contain many stock records / parts.
        """
        try:
            where = queryset.query.where
        except Exception:
            return None

        found = set()

        def walk(node):
            for child in getattr(node, "children", []):
                # Nested WhereNode
                if hasattr(child, "children"):
                    walk(child)
                    continue

                lhs = getattr(child, "lhs", None)
                rhs = getattr(child, "rhs", None)

                target = getattr(lhs, "target", None)
                field_name = getattr(target, "name", None)
                attname = getattr(target, "attname", None)

                if field_name == "consumed_by" or attname == "consumed_by_id":
                    pk = cls._coerce_pk(rhs)
                    if pk is not None:
                        found.add(pk)

        walk(where)

        if len(found) == 1:
            return next(iter(found))

        return None

    @classmethod
    def _resolve_build_id(cls, queryset, context):
        """Resolve exactly which Build Order the export was launched from.

        Resolution priority:
        1. Explicit Build Order in export context.
        2. Explicit `consumed_by` filter on the queryset.
        3. Fallback: all non-null consumed_by IDs represented in the queryset,
           but only when there is exactly one unique Build Order.

        Importantly, there is NO row / part limit here. Once the Build Order is
        known, the report engine evaluates every BuildLine in that Build Order.
        """
        build_id = cls._build_id_from_context(context)
        if build_id is not None:
            return build_id

        build_id = cls._build_id_from_queryset_filter(queryset)
        if build_id is not None:
            return build_id

        try:
            build_ids = list(
                queryset.exclude(consumed_by_id=None)
                .values_list("consumed_by_id", flat=True)
                .distinct()
            )
        except Exception:
            return None

        if len(build_ids) == 1:
            return cls._coerce_pk(build_ids[0])

        return None

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

        # build_spillage_report() iterates the Build Order's BuildLines, so all
        # BOM / build parts are evaluated. There is intentionally no 1-part,
        # 2-part, or StockItem count limit.
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
