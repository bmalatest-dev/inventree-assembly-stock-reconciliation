from __future__ import annotations

import inspect

from django.http import JsonResponse
from django.urls import path

from build.models import Build

from .plugin_v067 import (
    AssemblyStockReconciliationPlugin as ReconciliationV067Plugin,
)


class AssemblyStockReconciliationPlugin(ReconciliationV067Plugin):
    """v0.6.8 diagnostic release for InvenTree Build API compatibility."""

    VERSION = "0.6.8"

    def setup_urls(self):
        return [
            path("commit/", self.commit_reconciliation, name="commit"),
            path(
                "diagnostic/build-api/",
                self.build_api_diagnostic,
                name="build-api-diagnostic",
            ),
        ]

    def build_api_diagnostic(self, request):
        """Report the installed Build.complete_allocations API without modifying data."""
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            return JsonResponse({"detail": "Authentication required."}, status=401)

        method = Build.complete_allocations
        signature = inspect.signature(method)

        return JsonResponse(
            {
                "plugin_version": self.VERSION,
                "method": "Build.complete_allocations",
                "signature": str(signature),
                "parameters": [
                    {
                        "name": name,
                        "kind": str(parameter.kind),
                        "default": (
                            None
                            if parameter.default is inspect.Parameter.empty
                            else repr(parameter.default)
                        ),
                    }
                    for name, parameter in signature.parameters.items()
                ],
                "module": getattr(method, "__module__", None),
                "qualname": getattr(method, "__qualname__", None),
                "safe": True,
                "message": "Diagnostic only. No stock or build data was modified.",
            }
        )
