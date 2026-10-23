import { renderPanel as renderV0621 } from "./assembly_stock_reconciliation_ui_v0621.js";

const React = window.React;
const ReactDOM = window.ReactDOM;
const h = React.createElement;
const { useEffect, useState } = React;

/*
 * v0.6.23 UI placement fix.
 *
 * v0.6.22 attempted to insert Returned Stock Details by walking the React
 * element returned by the legacy panel. The legacy render function returns a
 * component element, not its rendered child tree, so Section 3 is not visible
 * to that traversal and the controls disappear entirely.
 *
 * Keep the proven v0.6.21 data / commit behavior unchanged. Once the legacy
 * panel is rendered, move the existing Returned Stock Details DOM block into
 * the Section 3 card. This is presentation-only: the React component, state,
 * event handlers and API payload behavior remain owned by v0.6.21.
 */
function SectionThreePlacement({ children }) {
  const [, setReady] = useState(false);

  useEffect(() => {
    let attempts = 0;

    const place = () => {
      attempts += 1;

      const headings = Array.from(document.querySelectorAll("h3"));
      const sectionHeading = headings.find((node) =>
        node.textContent?.trim() === "3. Enter physical return"
      );

      const detailHeading = Array.from(document.querySelectorAll("h4, h3")).find((node) =>
        node.textContent?.trim() === "Returned Stock Details"
      );

      const sectionCard = sectionHeading?.parentElement;
      const detailsBlock = detailHeading?.parentElement;

      if (sectionCard && detailsBlock && detailsBlock.parentElement !== sectionCard) {
        sectionCard.appendChild(detailsBlock);
        setReady(true);
        return;
      }

      if (sectionCard && detailsBlock) {
        setReady(true);
        return;
      }

      if (attempts < 50) window.setTimeout(place, 100);
    };

    place();
  }, []);

  return children;
}

export function renderPanel(context) {
  return h(SectionThreePlacement, null, renderV0621(context));
}
