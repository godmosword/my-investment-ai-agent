import BlockSectionShell from "./BlockSectionShell";

export default function TextSummaryBlock({ anchor, title, headerExtras, payload }) {
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="summary-block">{payload}</div>
    </BlockSectionShell>
  );
}
