import { renderPanel as renderV067 } from "./assembly_stock_reconciliation_ui_v067.js";

/*
 * v0.6.17 UI compatibility layer.
 *
 * A reconciliation with physical stock returned but zero build consumption is
 * not a no-op: the backend releases the selected BO allocation and moves the
 * returned stock to its selected location. The legacy UI labels this case as
 * "Confirm no-op reconciliation", which is misleading.
 *
 * Keep the proven v0.6.7/v0.5.3 UI and commit routing intact, but update the
 * operator-facing wording for this specific action. No validation or commit
 * behavior is bypassed here; the existing React button remains responsible for
 * enabled/disabled/submitting state and its original click handler.
 */
export function renderPanel(context) {
  const panel = renderV067(context);

  queueMicrotask(() => {
    const rewrite = () => {
      document.querySelectorAll("button").forEach((button) => {
        if (button.textContent?.trim() === "Confirm no-op reconciliation") {
          button.textContent = "Commit returned stock reconciliation";
          button.title = "Release the selected Build Order allocation and return the physical stock to the selected location.";
        }
      });
    };

    rewrite();

    const observer = new MutationObserver(rewrite);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });

    // The panel is normally long-lived, but avoid retaining the observer
    // indefinitely if the page is left open for an extended period.
    window.setTimeout(() => observer.disconnect(), 300000);
  });

  return panel;
}
