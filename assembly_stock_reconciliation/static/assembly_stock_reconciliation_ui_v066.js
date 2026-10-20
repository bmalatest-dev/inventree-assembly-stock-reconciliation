import { renderPanel as renderV053 } from "./assembly_stock_reconciliation_ui_v053.js";

export function renderPanel(context) {
  const originalApi = context.api;
  const compatibleApi = Object.create(originalApi);
  compatibleApi.post = function(url, payload, ...rest) {
    const isCommit =
      url === "/api/action/" &&
      payload?.action === "assembly_stock_reconciliation" &&
      payload?.data?.commit === true;
    if (isCommit) {
      return originalApi.post(
        "/plugin/assembly-stock-reconciliation/commit/",
        { data: payload.data },
        ...rest
      );
    }
    return originalApi.post(url, payload, ...rest);
  };
  return renderV053({ ...context, api: compatibleApi });
}
