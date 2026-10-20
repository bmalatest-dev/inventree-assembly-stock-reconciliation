from __future__ import annotations

import inspect

from django.http import JsonResponse
from django.urls import path

from build.models import Build

from .plugin_v069 import (
    AssemblyStockReconciliationPlugin as ReconciliationV069Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV069Plugin):
    """v0.6.10 diagnostic: inspect legacy stock-consumption API."""

    VERSION = "0.6.10"

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
        ]

    def subtract_allocated_stock_source_diagnostic(self, request):
        """
        Inspect Build.subtract_allocated_stock without executing it.

        This endpoint is diagnostic only and does not modify any
        build, allocation, or stock data.
        """

        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required."},
                status=401,
            )

        method = Build.subtract_allocated_stock

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
                "method": "Build.subtract_allocated_stock",
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