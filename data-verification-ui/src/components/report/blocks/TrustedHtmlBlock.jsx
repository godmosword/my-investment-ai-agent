import DOMPurify from "dompurify";
import BlockSectionShell from "./BlockSectionShell";

export default function TrustedHtmlBlock({ anchor, title, headerExtras, payload }) {
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div
        className="summary-block"
        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(String(payload ?? "")) }}
      />
    </BlockSectionShell>
  );
}
