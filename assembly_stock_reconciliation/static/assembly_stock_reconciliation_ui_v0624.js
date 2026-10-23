import { renderPanel as renderV0618 } from "./assembly_stock_reconciliation_ui_v0618.js";

/*
 * v0.6.24
 *
 * Keep the proven v0.6.18 reconciliation UI intact and add only the two
 * returned-stock metadata controls requested for Section 3. Previous attempts
 * tried to move React-owned elements after render. This version does not move
 * or rewrite the legacy React tree. It mounts a small native control block
 * directly into the existing Section 3 card and keeps its values in this
 * compatibility layer.
 */

function findSectionThreeCard() {
  const heading = Array.from(document.querySelectorAll("h3")).find(
    (node) => node.textContent?.trim() === "3. Enter physical return"
  );
  return heading?.parentElement || null;
}

function ensureReturnedStockControls(state) {
  const card = findSectionThreeCard();
  if (!card) return false;

  let root = card.querySelector("#assembly-stock-return-details-v0624");
  if (!root) {
    root = document.createElement("div");
    root.id = "assembly-stock-return-details-v0624";
    root.style.marginTop = "14px";
    root.style.paddingTop = "14px";
    root.style.borderTop = "1px solid var(--mantine-color-default-border, #d9d9d9)";

    const title = document.createElement("div");
    title.textContent = "Returned Stock Details";
    title.style.fontWeight = "600";
    title.style.marginBottom = "6px";
    root.appendChild(title);

    const help = document.createElement("div");
    help.textContent = "Confirm the packaging and stock status for material coming back from assembly. Returned material may no longer be machine loadable and may need to be moved to Rework and/or have its packaging or status changed.";
    help.style.fontSize = "13px";
    help.style.opacity = "0.78";
    help.style.marginBottom = "12px";
    root.appendChild(help);

    const grid = document.createElement("div");
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = "repeat(auto-fit, minmax(260px, 1fr))";
    grid.style.gap = "14px";

    const packagingWrap = document.createElement("div");
    const packagingLabel = document.createElement("label");
    packagingLabel.textContent = "Return Packaging";
    packagingLabel.style.display = "block";
    packagingLabel.style.fontWeight = "600";
    packagingLabel.style.marginBottom = "6px";
    const packagingInput = document.createElement("input");
    packagingInput.id = "assembly-stock-return-packaging-v0624";
    packagingInput.type = "text";
    packagingInput.style.width = "100%";
    packagingInput.style.maxWidth = "320px";
    packagingInput.style.padding = "9px 10px";
    packagingInput.style.borderRadius = "6px";
    packagingInput.style.border = "1px solid #b8b8b8";
    packagingInput.style.background = "var(--mantine-color-body, #fff)";
    packagingInput.style.color = "inherit";
    packagingInput.value = state.packaging;
    packagingInput.addEventListener("input", (event) => {
      state.packaging = event.target.value;
    });
    const packagingHelp = document.createElement("div");
    packagingHelp.textContent = "Leave unchanged if the returned material is still in the same packaging.";
    packagingHelp.style.fontSize = "12px";
    packagingHelp.style.opacity = "0.72";
    packagingHelp.style.marginTop = "5px";
    packagingWrap.append(packagingLabel, packagingInput, packagingHelp);

    const statusWrap = document.createElement("div");
    const statusLabel = document.createElement("label");
    statusLabel.textContent = "Return Stock Status";
    statusLabel.style.display = "block";
    statusLabel.style.fontWeight = "600";
    statusLabel.style.marginBottom = "6px";
    const statusSelect = document.createElement("select");
    statusSelect.id = "assembly-stock-return-status-v0624";
    statusSelect.style.width = "100%";
    statusSelect.style.maxWidth = "320px";
    statusSelect.style.padding = "9px 10px";
    statusSelect.style.borderRadius = "6px";
    statusSelect.style.border = "1px solid #b8b8b8";
    statusSelect.style.background = "var(--mantine-color-body, #fff)";
    statusSelect.style.color = "inherit";
    for (const option of state.statusOptions) {
      const el = document.createElement("option");
      el.value = String(option.value);
      el.textContent = option.label;
      statusSelect.appendChild(el);
    }
    statusSelect.value = state.status;
    statusSelect.addEventListener("change", (event) => {
      state.status = event.target.value;
    });
    const statusHelp = document.createElement("div");
    statusHelp.textContent = "Includes InvenTree standard and configured custom stock statuses.";
    statusHelp.style.fontSize = "12px";
    statusHelp.style.opacity = "0.72";
    statusHelp.style.marginTop = "5px";
    statusWrap.append(statusLabel, statusSelect, statusHelp);

    grid.append(packagingWrap, statusWrap);
    root.appendChild(grid);

    // Put the returned-stock metadata after Return Location and before notes.
    const notesLabel = Array.from(card.querySelectorAll("label")).find(
      (node) => node.textContent?.trim() === "Operator notes (optional)"
    );
    if (notesLabel) card.insertBefore(root, notesLabel);
    else card.appendChild(root);
  }

  const packagingInput = root.querySelector("#assembly-stock-return-packaging-v0624");
  if (packagingInput && document.activeElement !== packagingInput) {
    packagingInput.value = state.packaging;
  }

  const statusSelect = root.querySelector("#assembly-stock-return-status-v0624");
  if (statusSelect) {
    const existing = Array.from(statusSelect.options).map((o) => o.value).join("|");
    const desired = state.statusOptions.map((o) => String(o.value)).join("|");
    if (existing !== desired) {
      statusSelect.replaceChildren();
      for (const option of state.statusOptions) {
        const el = document.createElement("option");
        el.value = String(option.value);
        el.textContent = option.label;
        statusSelect.appendChild(el);
      }
    }
    statusSelect.value = state.status;
  }

  return true;
}

function addMetadataToItems(items, state) {
  if (!Array.isArray(items)) return items;
  return items.map((item) => ({
    ...item,
    return_packaging: state.packaging,
    return_status: state.status === "" ? null : Number(state.status),
  }));
}

export function renderPanel(context) {
  const state = {
    packaging: "",
    status: "",
    statusOptions: [],
    initialized: false,
  };

  const originalApi = context.api;
  const compatibleApi = Object.create(originalApi);

  compatibleApi.post = async function(url, payload, ...rest) {
    let outgoing = payload;

    // Normal preview path.
    if (
      url === "/api/action/"
      && payload?.action === "assembly_stock_reconciliation"
      && !payload?.data?.ui_context
      && Array.isArray(payload?.data?.items)
    ) {
      outgoing = {
        ...payload,
        data: {
          ...payload.data,
          items: addMetadataToItems(payload.data.items, state),
        },
      };
    }

    // v0.6.7+ rewrites commit requests to the dedicated endpoint before they
    // reach this outer compatibility API. Add the same metadata there too.
    if (
      url === "/plugin/assembly-stock-reconciliation/commit/"
      && Array.isArray(payload?.data?.items)
    ) {
      outgoing = {
        ...payload,
        data: {
          ...payload.data,
          items: addMetadataToItems(payload.data.items, state),
        },
      };
    }

    const response = await originalApi.post(url, outgoing, ...rest);

    const isUiContext =
      url === "/api/action/"
      && payload?.action === "assembly_stock_reconciliation"
      && payload?.data?.ui_context;

    if (isUiContext) {
      const result = response?.data?.result || response?.data;
      if (result?.ok) {
        state.statusOptions = result.stock_status_options || [];
        if (!state.initialized) {
          state.packaging = String(result.current_packaging || "");
          state.status = result.current_status == null ? "" : String(result.current_status);
          state.initialized = true;
        }
        queueMicrotask(() => ensureReturnedStockControls(state));
      }
    }

    return response;
  };

  const panel = renderV0618({
    ...context,
    api: compatibleApi,
  });

  // Section 3 is rendered by the legacy React component after this function
  // returns. Watch for it and ensure the controls remain present if React
  // re-renders the card during preview / refresh operations.
  queueMicrotask(() => {
    let attempts = 0;
    const mount = () => {
      attempts += 1;
      if (!ensureReturnedStockControls(state) && attempts < 100) {
        window.setTimeout(mount, 50);
      }
    };
    mount();

    const observer = new MutationObserver(() => ensureReturnedStockControls(state));
    observer.observe(document.body, { childList: true, subtree: true });
    window.setTimeout(() => observer.disconnect(), 300000);
  });

  return panel;
}
