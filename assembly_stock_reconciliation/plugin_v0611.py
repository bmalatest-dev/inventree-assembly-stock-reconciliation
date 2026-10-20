from __future__ import annotations

import inspect

from django.http import JsonResponse
from django.urls import path

from build.models import BuildItem

from .plugin_v0610 import (
    AssemblyStockReconciliationPlugin as ReconciliationV0610Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV0610Plugin):
    """v0.6.11 diagnostic: inspect legacy BuildItem consumption API."""

    VERSION = "0.6.11"

    def setup_urls(self):
        return [
            path(
                "commit/",
                self.commit_reconciliation,
                name="commit",
            ),
            path(
                "diagnostic/build-api/",
                self.build_api_diagnostic,
                name="build-api-diagnostic",
            ),
            path(
                "diagnostic/build-api-source/",
                self.build_api_source_diagnostic,
                name="build-api-source-diagnostic",
            ),
            path(
                "diagnostic/subtract-allocated-stock-source/",
                self.subtract_allocated_stock_source_diagnostic,
                name="subtract-allocated-stock-source-diagnostic",
            ),
            path(
                "diagnostic/build-item-complete-allocation-source/",
                self.build_item_complete_allocation_source_diagnostic,
                name="build-item-complete-allocation-source-diagnostic",
            ),
        ]

    def build_item_complete_allocation_source_diagnostic(self, request):
        """
        Inspect BuildItem.complete_allocation without executing it.

        Diagnostic only. No stock, allocation, or build data is modified.
        """

        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required."},
                status=401,
            )

        method = BuildItem.complete_allocation

        try:
            signature = str(inspect.signature(method))
            signature_error = None
        except (ValueError, TypeError) as exc:
            signature = None
            signature_error = f"{type(exc).__name__}: {exc}"

        try:
            source = inspect.getsource(method)
            source_error = None
        except (OSError, TypeError) as exc:
            source = None
            source_error = f"{type(exc).__name__}: {exc}"

        try:
            source_file = inspect.getsourcefile(method)
        except (OSError, TypeError):
            source_file = None

        return JsonResponse(
            {
                "plugin_version": self.VERSION,
                "method": "BuildItem.complete_allocation",
                "signature": signature,
                "signature_error": signature_error,
                "module": getattr(method, "__module__", None),
                "qualname": getattr(method, "__qualname__", None),
                "source_file": source_file,
                "source": source,
                "source_error": source_error,
                "safe": True,
                "message": (
                    "Diagnostic only. The method was inspected, not executed. "
                    "No stock, allocation, or build data was modified."
                ),
            }
        )