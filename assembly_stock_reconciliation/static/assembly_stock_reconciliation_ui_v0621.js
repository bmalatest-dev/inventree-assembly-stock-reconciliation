import { renderPanel as renderV0618 } from "./assembly_stock_reconciliation_ui_v0618.js";

const React = window.React;
const h = React.createElement;
const { useMemo, useRef, useState } = React;

const cardStyle = {
  maxWidth: "1050px",
  border: "1px solid var(--mantine-color-default-border, #d9d9d9)",
  borderRadius: "8px",
  padding: "16px",
  marginBottom: "16px",
  background: "var(--mantine-color-body, transparent)"
};

const inputStyle = {
  width: "100%",
  maxWidth: "360px",
  padding: "9px 10px",
  borderRadius: "6px",
  border: "1px solid #b8b8b8",
  background: "var(--mantine-color-body, #fff)",
  color: "inherit"
};

function ReturnedStockDetails({ context }) {
  const [meta, setMeta] = useState(null);
  const [packaging, setPackaging] = useState("");
  const [status, setStatus] = useState("");
  const packagingRef = useRef("");
  const statusRef = useRef("");
  const initializedRef = useRef(false);

  const compatibleApi = useMemo(() => {
    const originalApi = context.api;
    const api = Object.create(originalApi);

    api.post = async function(url, payload, ...rest) {
      const isPluginAction = url === "/api/action/"
        && payload?.action === "assembly_stock_reconciliation";
      const isUiContext = isPluginAction && payload?.data?.ui_context;

      if (isPluginAction && !isUiContext && Array.isArray(payload?.data?.items)) {
        payload = {
          ...payload,
          data: {
            ...payload.data,
            items: payload.data.items.map((item) => ({
              ...item,
              return_packaging: packagingRef.current,
              return_status: statusRef.current === "" ? null : Number(statusRef.current)
            }))
          }
        };
      }

      const response = await originalApi.post(url, payload, ...rest);

      if (isUiContext) {
        const result = response?.data?.result || response?.data;
        if (result?.ok) {
          setMeta(result);

          // Initialize once from the Stock Item. Do not overwrite an operator's
          // selection when the underlying v0.6.18 UI refreshes its context.
          if (!initializedRef.current) {
            const initialPackaging = String(result.current_packaging || "");
            const initialStatus = result.current_status == null
              ? ""
              : String(result.current_status);

            packagingRef.current = initialPackaging;
            statusRef.current = initialStatus;
            setPackaging(initialPackaging);
            setStatus(initialStatus);
            initializedRef.current = true;
          }
        }
      }

      return response;
    };

    return api;
  }, [context.api]);

  const panel = renderV0618({
    ...context,
    api: compatibleApi
  });

  return h("div", null,
    h("div", { style: cardStyle },
      h("h3", { style: { marginTop: 0, marginBottom: "6px" } }, "Returned Stock Details"),
      h("p", { style: { marginTop: 0, opacity: 0.78 } },
        "Confirm the packaging and stock status for material coming back from assembly. Returned material may no longer be machine loadable and may need to be moved to Rework and/or have its packaging or status changed."
      ),
      !meta
        ? h("div", { style: { opacity: 0.7 } }, "Loading current packaging and status…")
        : h("div", {
            style: {
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "16px"
            }
          },
            h("div", null,
              h("label", { style: { display: "block", marginBottom: "6px", fontWeight: 600 } },
                "Return Packaging"
              ),
              h("input", {
                style: inputStyle,
                type: "text",
                value: packaging,
                placeholder: "Packaging",
                onChange: (event) => {
                  const value = event.target.value;
                  packagingRef.current = value;
                  setPackaging(value);
                }
              }),
              h("div", { style: { marginTop: "5px", fontSize: "12px", opacity: 0.72 } },
                "Leave unchanged if the returned material is still in the same packaging."
              )
            ),
            h("div", null,
              h("label", { style: { display: "block", marginBottom: "6px", fontWeight: 600 } },
                "Return Stock Status"
              ),
              h("select", {
                style: inputStyle,
                value: status,
                onChange: (event) => {
                  const value = event.target.value;
                  statusRef.current = value;
                  setStatus(value);
                }
              },
                ...(meta.stock_status_options || []).map((option) =>
                  h("option", { key: option.value, value: String(option.value) }, option.label)
                )
              ),
              h("div", { style: { marginTop: "5px", fontSize: "12px", opacity: 0.72 } },
                "Includes InvenTree standard and configured custom stock statuses."
              )
            )
          )
    ),
    panel
  );
}

export function renderPanel(context) {
  return h(ReturnedStockDetails, { context });
}
