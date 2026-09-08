from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import path

from plugin.mixins import UrlsMixin

from .plugin import AssemblyStockReconciliationPlugin as ReconciliationV053Plugin
from .spillage_report import build_spillage_report, report_to_csv


class AssemblyStockReconciliationPlugin(UrlsMixin, ReconciliationV053Plugin):
    """v0.6.0 wrapper around the validated v0.5.3 reconciliation plugin.

    The existing reconciliation workflow remains unchanged. This class adds
    a read-only Build Order post-assembly spillage report and becomes the
    package entry point for v0.6.0.
    """

    VERSION = "0.6.0"

    def setup_urls(self):
        """Expose the downloadable Build Order spillage report."""
        return [
            path(
                "spillage-report/<int:build_id>.csv",
                self.download_spillage_report,
                name="post-assembly-spillage-report",
            ),
        ]

    @login_required
    def download_spillage_report(self, request, build_id):
        """Download exception-only post-assembly spillage report for a BO."""
        if not request.user.has_perm("build.view_build"):
            return HttpResponseForbidden(
                "You do not have permission to view Build Orders."
            )

        report = build_spillage_report(build_id)

        response = HttpResponse(
            report_to_csv(report),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="post-assembly-spillage-'
            f'{report["build_reference"]}.csv"'
        )

        return response

    def get_ui_primary_actions(self, request, context, **kwargs):
        """Add a Post Assembly Spillage Report action to Build Order pages."""
        context = context or {}

        target_model = str(context.get("target_model") or "").casefold()
        target_id = context.get("target_id")

        if target_model not in {"build", "buildorder"} or not target_id:
            return []

        return [
            {
                "key": "post-assembly-spillage-report",
                "title": "Post Assembly Spillage Report",
                "description": (
                    "Download material consumption above the approved "
                    "Build Order spillage allowance."
                ),
                "icon": "ti:file-spreadsheet:outline",
                "options": {
                    "url": (
                        f"/plugin/{self.SLUG}/spillage-report/"
                        f"{int(target_id)}.csv"
                    ),
                },
            }
        ]
