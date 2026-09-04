const React = window.React;
const h = React.createElement;
const { useEffect, useMemo, useState } = React;

const styles = {
  panel: { maxWidth: "1050px", display: "grid", gap: "16px" },
  card: {
    border: "1px solid var(--mantine-color-default-border, #d9d9d9)",
    borderRadius: "8px",
    padding: "16px",
    background: "var(--mantine-color-body, transparent)"
  },
  row: { display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px"
  },
  stat: {
    border: "1px solid var(--mantine-color-default-border, #e2e2e2)",
    borderRadius: "6px",
    padding: "10px"
  },
  label: { fontSize: "12px", opacity: 0.72, marginBottom: "4px" },
  value: { fontWeight: 600, fontSize: "16px" },
  input: {
    width: "100%",
    maxWidth: "320px",
    padding: "9px 10px",
    borderRadius: "6px",
    border: "1px solid #b8b8b8",
    background: "var(--mantine-color-body, #fff)",
    color: "inherit"
  },
  textarea: {
    width: "100%",
    minHeight: "76px",
    padding: "9px 10px",
    borderRadius: "6px",
    border: "1px solid #b8b8b8",
    background: "var(--mantine-color-body, #fff)",
    color: "inherit"
  },
  button: {
    border: 0,
    borderRadius: "6px",
    padding: "9px 14px",
    cursor: "pointer",
    fontWeight: 600
  },
  primary: { background: "#1971c2", color: "white" },
  success: { background: "#2b8a3e", color: "white" },
  danger: { background: "#c92a2a", color: "white" },
  secondary: {
    background: "var(--mantine-color-default, #e9ecef)",
    color: "inherit",
    border: "1px solid var(--mantine-color-default-border, #ced4da)"
  },
  alertWarn: {
    border: "1px solid #f08c00",
    background: "rgba(240, 140, 0, 0.10)",
    borderRadius: "6px",
    padding: "12px"
  },
  alertError: {
    border: "1px solid #c92a2a",
    background: "rgba(201, 42, 42, 0.10)",
    borderRadius: "6px",
    padding: "12px"
  },
  alertSuccess: {
    border: "1px solid #2b8a3e",
    background: "rgba(43, 138, 62, 0.10)",
    borderRadius: "6px",
    padding: "12px"
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: { textAlign: "left", padding: "8px", borderBottom: "1px solid #bbb", fontSize: "13px" },
  td: { padding: "8px", borderBottom: "1px solid #ddd", fontSize: "13px" }
};

function buttonStyle(kind, disabled) {
  return Object.assign(
    {},
    styles.button,
    styles[kind] || styles.primary,
    disabled ? { opacity: 0.45, cursor: "not-allowed" } : {}
  );
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return Number.isInteger(n) ? String(n) : String(Number(n.toFixed(5)));
}

function Alert({ kind = "warn", children }) {
  const style = kind === "error" ? styles.alertError
    : kind === "success" ? styles.alertSuccess
    : styles.alertWarn;
  return h("div", { style }, children);
}

function SummaryStat({ label, value }) {
  return h("div", { style: styles.stat },
    h("div", { style: styles.label }, label),
    h("div", { style: styles.value }, value)
  );
}

function ReconciliationPanel({ context }) {
  const stockItemId = Number(
    context?.context?.stock_item_id || context?.id || context?.context?.target_id
  );

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [stock, setStock] = useState(null);
  const [selectedBuilds, setSelectedBuilds] = useState([]);
  const [returnedQty, setReturnedQty] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [overrideChecked, setOverrideChecked] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [returnLocation, setReturnLocation] = useState("");
  const [returnLocationText, setReturnLocationText] = useState("");

  async function loadContext(resetSelection = false) {
    setLoading(true);
    setError("");
    try {
      const response = await context.api.post("/api/action/", {
        action: "assembly_stock_reconciliation",
        data: { ui_context: true, stock_item: stockItemId }
      });
      const result = response?.data?.result || response?.data;
      if (!result?.ok) {
        throw new Error(result?.message || "Could not load reconciliation data.");
      }
      setStock(result);
      if (resetSelection) {
        setReturnLocation(result.recommended_return_location ? String(result.recommended_return_location) : "");
        setReturnLocationText(result.recommended_return_location_path || "");
      } else if (!returnLocation) {
        setReturnLocation(result.recommended_return_location ? String(result.recommended_return_location) : "");
        setReturnLocationText(result.recommended_return_location_path || "");
      }
      if (resetSelection) {
        setSelectedBuilds([]);
      } else {
        setSelectedBuilds((current) =>
          current.filter((id) => result.builds.some((b) => b.build === id))
        );
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (stockItemId) loadContext();
    else {
      setError("No Stock Item ID was supplied to the plugin panel.");
      setLoading(false);
    }
  }, [stockItemId]);

  function invalidatePreview() {
    setPreview(null);
    setSuccess("");
    setOverrideChecked(false);
    setOverrideReason("");
  }

  function toggleBuild(id) {
    invalidatePreview();
    setSelectedBuilds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id]
    );
  }

  const selectedAllocation = useMemo(() => {
    if (!stock) return 0;
    return stock.builds
      .filter((b) => selectedBuilds.includes(b.build))
      .reduce((sum, b) => sum + Number(b.allocated || 0), 0);
  }, [stock, selectedBuilds]);

  const canPreview = selectedBuilds.length > 0
    && returnedQty !== ""
    && Number(returnedQty) >= 0
    && (Number(returnedQty) === 0 || !!returnLocation);

  async function runAction(commit, useOverride = false) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        action: "assembly_stock_reconciliation",
        data: {
          commit,
          notes,
          items: [{
            stock_item: stockItemId,
            builds: [...selectedBuilds].sort((a, b) => a - b),
            returned_quantity: returnedQty,
            return_location: returnLocation || null
          }]
        }
      };

      if (useOverride) {
        payload.data.override_policy_warning = true;
        payload.data.override_reason = overrideReason.trim();
      }

      const response = await context.api.post("/api/action/", payload);
      const result = response?.data?.result || response?.data;
      setPreview(result);

      if (commit && result?.committed) {
        setSuccess(
          result.override_used
            ? "Reconciliation committed with explicit override."
            : "Reconciliation committed successfully."
        );
        await loadContext(true);
        setReturnedQty("");
        setNotes("");
        setOverrideChecked(false);
        setOverrideReason("");
        setReturnLocation("");
        setReturnLocationText("");
        if (typeof context.reloadInstance === "function") context.reloadInstance();
        if (typeof context.reloadContent === "function") context.reloadContent();
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.response?.data || err?.message || String(err);
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return h("div", null, "Loading Assembly Stock Reconciliation…");
  if (!stock) return h(Alert, { kind: "error" }, error || "Unable to load Stock Item.");

  const itemPreview = preview?.items?.[0];
  const hardWarning = !!preview?.override_required || !!itemPreview?.hard_warning;
  const blocking = !!itemPreview?.blocking_error;
  const ready = preview && !blocking && !hardWarning && preview.ok && !preview.committed;
  const noOp = itemPreview && Number(itemPreview.calculated_consumption || 0) === 0;
  const overrideReady = hardWarning && !blocking && overrideChecked && overrideReason.trim().length > 0;

  return h("div", { style: styles.panel },
    h("div", { style: styles.card },
      h("div", { style: styles.grid },
        h(SummaryStat, { label: "Stock Item", value: `#${stock.stock_item}` }),
        h(SummaryStat, { label: "Part", value: stock.part || "—" }),
        h(SummaryStat, { label: "Current Quantity", value: fmt(stock.current_quantity) }),
        h(SummaryStat, { label: "Batch", value: stock.batch || "—" }),
        h(SummaryStat, { label: "Current Location", value: stock.current_location_path || "—" }),
        h(SummaryStat, { label: "Case / Package", value: stock.case_package || "—" }),
        h(SummaryStat, { label: "Part Pricing Max", value: Number(stock.part_pricing_max || 0) > 0 ? fmt(stock.part_pricing_max) : "—" }),
        h(SummaryStat, { label: "Stock Item Unit Price", value: Number(stock.stock_unit_price || 0) > 0 ? fmt(stock.stock_unit_price) : "—" }),
        h(SummaryStat, { label: "Effective Policy Price", value: Number(stock.effective_price || 0) > 0 ? fmt(stock.effective_price) : "Missing / zero" }),
        h(SummaryStat, { label: "Price Source", value: String(stock.price_source || "—").replaceAll("_", " ") }),
        h(SummaryStat, { label: "Planned Spillage / BO", value: fmt(stock.spillage_per_project) }),
        h(SummaryStat, { label: "Spillage Rule", value: stock.spillage_rule || "—" })
      )
    ),

    h("div", { style: styles.card },
      h("h3", { style: { marginTop: 0 } }, "1. Select relevant Build Orders"),
      h("p", { style: { marginTop: 0, opacity: 0.78 } },
        "Select every Build Order whose allocations represent material physically sent with this stock item. Consumption is attributed in BO order."
      ),
      stock.builds.length === 0
        ? h(Alert, { kind: "warn" }, "This Stock Item has no remaining Build Order allocations.")
        : h(React.Fragment, null,
            h("div", { style: { ...styles.row, marginBottom: "10px" } },
              h("button", {
                type: "button",
                style: buttonStyle("secondary", false),
                onClick: () => {
                  invalidatePreview();
                  setSelectedBuilds(stock.builds.map((b) => b.build));
                }
              }, "Select all"),
              h("button", {
                type: "button",
                style: buttonStyle("secondary", false),
                onClick: () => {
                  invalidatePreview();
                  setSelectedBuilds([]);
                }
              }, "Clear")
            ),
            ...stock.builds.map((b) =>
              h("label", {
                key: b.build,
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: "9px",
                  padding: "8px 0",
                  cursor: "pointer"
                }
              },
                h("input", {
                  type: "checkbox",
                  checked: selectedBuilds.includes(b.build),
                  onChange: () => toggleBuild(b.build)
                }),
                h("strong", null, b.reference),
                h("span", { style: { opacity: 0.72 } }, `Remaining allocation: ${fmt(b.allocated)}`)
              )
            ),
            h("div", { style: { marginTop: "10px", fontWeight: 600 } },
              `Selected allocation total: ${fmt(selectedAllocation)}`
            )
          )
    ),

    h("div", { style: styles.card },
      h("h3", { style: { marginTop: 0 } }, "2. Enter physical return"),
      h("label", { style: { display: "block", marginBottom: "6px", fontWeight: 600 } },
        "Physical quantity returned"
      ),
      h("input", {
        type: "number",
        min: "0",
        step: "any",
        value: returnedQty,
        style: styles.input,
        onChange: (e) => {
          invalidatePreview();
          setReturnedQty(e.target.value);
        }
      }),

      h("div", { style: { marginTop: "14px" } },
        h("label", { style: { display: "block", marginBottom: "6px", fontWeight: 600 } },
          "Return location"
        ),
        stock.recommended_return_location
          ? h("div", { style: { marginBottom: "8px", fontSize: "13px" } },
              h("strong", null, "Recommended: "),
              stock.recommended_return_location_path
            )
          : h("div", { style: { marginBottom: "8px", fontSize: "13px", opacity: 0.75 } },
              "No non-temporary location could be identified from recent history. Select a return location."
            ),
        stock.recent_locations?.length
          ? h("div", { style: { marginBottom: "10px", fontSize: "13px" } },
              h("div", { style: { fontWeight: 600, marginBottom: "4px" } }, "Recent locations"),
              ...stock.recent_locations.map((loc) =>
                h("button", {
                  key: `recent-${loc.location}`,
                  type: "button",
                  style: {
                    ...buttonStyle("secondary", false),
                    padding: "5px 8px",
                    margin: "0 6px 6px 0",
                    fontWeight: loc.recommended ? 700 : 500
                  },
                  title: loc.transient ? "Temporary / transient location" : "Recent storage location",
                  onClick: () => {
                    invalidatePreview();
                    setReturnLocation(String(loc.location));
                    setReturnLocationText(loc.path);
                  }
                }, `${loc.path}${loc.date ? ` — ${new Date(loc.date).toLocaleDateString()}` : ""}${loc.recommended ? " (recommended)" : ""}`)
              )
            )
          : null,
        h("input", {
          list: `stock-rec-locations-${stockItemId}`,
          value: returnLocationText,
          style: { ...styles.input, maxWidth: "600px" },
          placeholder: "Search or select a Stock Location",
          onChange: (e) => {
            invalidatePreview();
            const text = e.target.value;
            setReturnLocationText(text);
            const match = stock.return_locations?.find((loc) => loc.path === text);
            setReturnLocation(match ? String(match.location) : "");
          }
        }),
        h("datalist", { id: `stock-rec-locations-${stockItemId}` },
          ...(stock.return_locations || []).map((loc) =>
            h("option", { key: loc.location, value: loc.path })
          )
        ),
        returnLocation
          ? h("div", { style: { marginTop: "5px", fontSize: "12px", opacity: 0.72 } },
              `Selected: ${returnLocationText}`
            )
          : null
      ),
      h("label", { style: { display: "block", margin: "14px 0 6px", fontWeight: 600 } },
        "Operator notes (optional)"
      ),
      h("textarea", {
        value: notes,
        style: styles.textarea,
        placeholder: "Optional notes to include in the stock tracking audit trail",
        onChange: (e) => {
          invalidatePreview();
          setNotes(e.target.value);
        }
      }),
      h("div", { style: { ...styles.row, marginTop: "14px" } },
        h("button", {
          type: "button",
          disabled: !canPreview || submitting,
          style: buttonStyle("primary", !canPreview || submitting),
          onClick: () => runAction(false, false)
        }, submitting ? "Working…" : "Preview reconciliation")
      )
    ),

    error ? h(Alert, { kind: "error" }, error) : null,
    success ? h(Alert, { kind: "success" }, success) : null,

    itemPreview ? h("div", { style: styles.card },
      h("h3", { style: { marginTop: 0 } }, "3. Review reconciliation"),
      h("div", { style: styles.grid },
        h(SummaryStat, { label: "Starting Quantity", value: fmt(itemPreview.current_quantity) }),
        h(SummaryStat, { label: "Returned Quantity", value: fmt(itemPreview.returned_quantity) }),
        h(SummaryStat, { label: "Return Location", value: itemPreview.return_location_path || "—" }),
        h(SummaryStat, { label: "Selected Allocations", value: fmt(itemPreview.selected_allocation_quantity) }),
        h(SummaryStat, { label: "Calculated Consumption", value: fmt(itemPreview.calculated_consumption) }),
        h(SummaryStat, { label: "Nominal Expected Consumption", value: fmt(itemPreview.nominal_expected_consumption) }),
        h(SummaryStat, { label: "Planned Spillage / Overage", value: fmt(itemPreview.planned_spillage_allowance) }),
        h(SummaryStat, { label: "Maximum Acceptable Consumption", value: fmt(itemPreview.acceptable_consumption_max) }),
        h(SummaryStat, { label: "Planned JIT Allocation on Commit", value: fmt(itemPreview.planned_jit_allocation_required) }),
        h(SummaryStat, { label: "Exception Allocation on Override", value: fmt(itemPreview.exception_allocation_required) }),
        h(SummaryStat, { label: "Planned Spillage Used", value: fmt(itemPreview.planned_spillage_consumed) }),
        h(SummaryStat, { label: "Exception Quantity", value: fmt(itemPreview.exception_consumed) }),
        h(SummaryStat, { label: "Expected Return Range", value: `${fmt(itemPreview.expected_return_min)} to ${fmt(itemPreview.expected_return_max)}` }),
        h(SummaryStat, { label: "Policy Result", value: String(itemPreview.policy_classification || "—").replaceAll("_", " ") }),
        h(SummaryStat, { label: "Effective Policy Price", value: Number(itemPreview.effective_price || 0) > 0 ? fmt(itemPreview.effective_price) : "Missing / zero" }),
        h(SummaryStat, { label: "Price Source", value: String(itemPreview.price_source || "—").replaceAll("_", " ") }),
        h(SummaryStat, { label: "Spillage Rule", value: itemPreview.spillage_rule || "—" })
      ),

      itemPreview.messages?.length
        ? h("div", { style: { marginTop: "12px" } },
            ...itemPreview.messages.map((m, i) =>
              h(Alert, { key: i, kind: blocking ? "error" : hardWarning ? "warn" : "success" }, m)
            )
          )
        : null,

      itemPreview.consumption_plan?.length
        ? h("div", { style: { marginTop: "14px", overflowX: "auto" } },
            h("table", { style: styles.table },
              h("thead", null,
                h("tr", null,
                  h("th", { style: styles.th }, "Order"),
                  h("th", { style: styles.th }, "Build Order"),
                  h("th", { style: styles.th }, "Existing Allocation"),
                  h("th", { style: styles.th }, "Planned JIT"),
                  h("th", { style: styles.th }, "Exception Allocation"),
                  h("th", { style: styles.th }, "Consume")
                )
              ),
              h("tbody", null,
                ...itemPreview.consumption_plan.map((line, i) =>
                  h("tr", { key: `${line.build_item}-${i}` },
                    h("td", { style: styles.td }, i + 1),
                    h("td", { style: styles.td }, line.build_reference),
                    h("td", { style: styles.td }, fmt(line.allocated)),
                    h("td", { style: styles.td }, fmt(line.planned_jit_allocation_required)),
                    h("td", { style: styles.td }, fmt(line.exception_allocation_required)),
                    h("td", { style: styles.td }, fmt(line.consume))
                  )
                )
              )
            )
          )
        : noOp
          ? h(Alert, { kind: "success" }, "No stock consumption is required.")
          : null,

      blocking
        ? h(Alert, { kind: "error" },
            "This reconciliation is blocked. Correct the Build Order selection or investigate the discrepancy before proceeding."
          )
        : null,

      hardWarning && !blocking
        ? h("div", { style: { ...styles.alertWarn, marginTop: "14px" } },
            h("strong", null, "HARD WARNING — investigation and explicit approval required"),
            h("p", null,
              "Actual consumption falls outside the nominal-to-planned-spillage range. Planned spillage and exception quantity are shown separately. Do not override until the manufacturing discrepancy has been investigated."
            ),
            h("label", { style: { display: "flex", gap: "8px", alignItems: "flex-start", marginBottom: "10px" } },
              h("input", {
                type: "checkbox",
                checked: overrideChecked,
                onChange: (e) => setOverrideChecked(e.target.checked)
              }),
              h("span", null, "I have investigated this discrepancy and expressly approve the override.")
            ),
            h("label", { style: { display: "block", marginBottom: "6px", fontWeight: 600 } },
              "Override reason"
            ),
            h("textarea", {
              value: overrideReason,
              style: styles.textarea,
              placeholder: "Required: explain why this reconciliation is being approved despite the discrepancy",
              onChange: (e) => setOverrideReason(e.target.value)
            })
          )
        : null,

      h("div", { style: { ...styles.row, marginTop: "16px" } },
        ready
          ? h("button", {
              type: "button",
              disabled: submitting,
              style: buttonStyle("success", submitting),
              onClick: () => {
                if (window.confirm("Commit this stock reconciliation? This will consume stock in InvenTree.")) {
                  runAction(true, false);
                }
              }
            }, noOp ? "Confirm no-op reconciliation" : "Commit reconciliation")
          : null,
        hardWarning && !blocking
          ? h("button", {
              type: "button",
              disabled: !overrideReady || submitting,
              style: buttonStyle("danger", !overrideReady || submitting),
              onClick: () => {
                if (window.confirm(
                  "Commit this reconciliation WITH OVERRIDE? The override reason will be recorded in Stock Tracking."
                )) {
                  runAction(true, true);
                }
              }
            }, "Commit with override")
          : null,
        h("button", {
          type: "button",
          disabled: submitting,
          style: buttonStyle("secondary", submitting),
          onClick: () => {
            setPreview(null);
            setError("");
            setSuccess("");
            loadContext();
          }
        }, "Refresh")
      )
    ) : null,

    h("div", { style: { fontSize: "12px", opacity: 0.65 } },
      `Assembly Stock Reconciliation v${context?.context?.plugin_version || "0.4.1"}`
    )
  );
}

export function renderPanel(context) {
  return h(ReconciliationPanel, { context });
}
