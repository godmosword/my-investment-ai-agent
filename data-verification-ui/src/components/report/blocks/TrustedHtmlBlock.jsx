import BlockSectionShell from "./BlockSectionShell";

/** BQ／管線組裝 HTML（與 Telegram 模板同源信任邊界）。 */
export default function TrustedHtmlBlock({ anchor, title, headerExtras, payload }) {
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="summary-block" dangerouslySetInnerHTML={{ __html: String(payload ?? "") }} />
    </BlockSectionShell>
  );
}
