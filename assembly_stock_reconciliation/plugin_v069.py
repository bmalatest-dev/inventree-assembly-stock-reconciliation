from __future__ import annotations

import inspect

from django.http import JsonResponse
from django.urls import path

from build.models import Build

from .plugin_v068 import (
    AssemblyStockReconciliationPlugin as ReconciliationV068Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV068Plugin):
    """v0.6.9 diagnostic: safely expose complete_allocations source."""

    VERSION = "0.6.9"

    def setup_urls(self):
        return [
            path("commit/", self.commit_reconciliation, name="commit"),
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
        ]

    def build_api_source_diagnostic(self, request):
        """Inspect Build.complete_allocations without executing it."""

        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required."},
                status=401,
            )

        method = Build.complete_allocations

        try:
            source = inspect.getsource(method)
            source_error = None
        except (OSError, TypeError) as exc:
            source = None
            source_error = f"{type(exc).__name__}: {exc}"

        return JsonResponse(
            {
                "plugin_version": self.VERSION,
                "method": "Build.complete_allocations",
                "signature": str(inspect.signature(method)),
                "module": getattr(method, "__module__", None),
                "qualname": getattr(method, "__qualname__", None),
                "source": source,
                "source_error": source_error,
                "safe": True,
                "message": (
                    "Diagnostic only. The method was inspected, not executed. "
                    "No stock or build data was modified."
                ),
            }
        )