import BlockSectionShell from "./BlockSectionShell";

export default function InstitutionalViewBlock({ anchor, title, headerExtras, payload }) {
  const { thesisText, disclaimerHtml } = payload ?? {};
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      {thesisText ? (
        <div className="summary-block" style={{ whiteSpace: "pre-wrap" }}>
          {thesisText}
        </div>
      ) : null}
      {disclaimerHtml ? (
        <div
          className="summary-block"
          style={{ marginTop: thesisText ? 10 : 0 }}
          dangerouslySetInnerHTML={{ __html: String(disclaimerHtml) }}
        />
      ) : null}
    </BlockSectionShell>
  );
}
