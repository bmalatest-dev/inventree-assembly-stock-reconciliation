import { renderPanel as renderV0617 } from "./assembly_stock_reconciliation_ui_v0617.js";

/*
 * v0.6.18 UI compatibility layer.
 *
 * Reconciliation changes stock quantity / consumption / allocation state in
 * the backend, but the surrounding InvenTree Stock Item page can retain the
 * pre-commit instance data. This leaves the page-level AVAILABLE value stale
 * until the operator manually refreshes the page.
 *
 * Keep all v0.6.17 reconciliation behavior intact. After the plugin commit
 * endpoint confirms a successful commit, reload the Stock Item page so
 * InvenTree re-fetches the current stock state and recalculates availability.
 */
export function renderPanel(context) {
  const originalApi = context.api;
  const compatibleApi = Object.create(originalApi);

  compatibleApi.post = async function(url, payload, ...rest) {
    const response = await originalApi.post(url, payload, ...rest);

    const isReconciliationCommit =
      url === "/plugin/assembly-stock-reconciliation/commit/";

    if (isReconciliationCommit) {
      const result = response?.data?.result || response?.data;

      if (result?.committed) {
        // Allow the successful response to settle, then refresh the complete
        // Stock Item page. This updates page-level Quantity / Available /
        // allocation data which lives outside the plugin React panel.
        window.setTimeout(() => window.location.reload(), 250);
      }
    }

    return response;
  };

  return renderV0617({
    ...context,
    api: compatibleApi,
  });
}
