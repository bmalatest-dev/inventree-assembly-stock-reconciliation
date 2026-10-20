from __future__ import annotations
import json
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import path
from plugin.mixins import UrlsMixin
from .plugin_v065 import AssemblyStockReconciliationPlugin as ReconciliationV065Plugin

class AssemblyStockReconciliationPlugin(UrlsMixin, ReconciliationV065Plugin):
    VERSION = "0.6.6"

    def setup_urls(self):
        return [path("commit/", self.commit_reconciliation, name="commit")]

    def get_ui_panels(self, request, context, **kwargs):
        context = context or {}
        target_model = context.get("target_model")
        target_id = context.get("target_id")
        if target_model != "stockitem" or not target_id:
            return []
        return [{
            "key": "assembly-stock-reconciliation",
            "title": "Assembly Stock Reconciliation",
            "description": "Reconcile stock returned from external assembly against selected Build Orders.",
            "icon": "ti:arrows-exchange:outline",
            "source": self.plugin_static_file("assembly_stock_reconciliation_ui_v066.js:renderPanel"),
            "context": {"stock_item_id": target_id, "plugin_version": self.VERSION},
        }]

    def commit_reconciliation(self, request):
        if request.method != "POST":
            return JsonResponse({"detail": "POST required."}, status=405)
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return JsonResponse({"detail": "Authentication required."}, status=401)
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"detail": "Invalid JSON request body."}, status=400)
        data = body.get("data", body)
        if not isinstance(data, dict):
            return JsonResponse({"detail": "Request data must be a JSON object."}, status=400)
        data = dict(data)
        data["commit"] = True
        try:
            result = self._run(user=user, data=data)
        except ValidationError as exc:
            detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None) or str(exc)
            return JsonResponse({"detail": detail}, status=400)
        except Exception as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        return JsonResponse({"result": result})
