import BlockSectionShell from "./BlockSectionShell";

function citationText(citations) {
  const first = Array.isArray(citations) ? citations[0] : null;
  if (!first) return "";
  const page = first.page ? ` p.${first.page}` : "";
  return [first.section, first.excerpt, page].filter(Boolean).join(" · ");
}

export default function DeepFilingBlock({ anchor, title, headerExtras, payload }) {
  const answers = payload?.answers && typeof payload.answers === "object" ? Object.entries(payload.answers) : [];
  const citations = payload?.citations && typeof payload.citations === "object" ? payload.citations : {};

  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="summary-block">
        {payload?.ticker || payload?.filing_type ? (
          <div style={{ marginBottom: 10, fontWeight: 700 }}>
            {[payload?.ticker, payload?.filing_type].filter(Boolean).join(" · ")}
          </div>
        ) : null}
        <div style={{ display: "grid", gap: 10 }}>
          {answers.map(([key, value]) => {
            const cite = citationText(citations[key]);
            return (
              <div key={key}>
                <div style={{ fontWeight: 700 }}>Q{key}</div>
                <div style={{ whiteSpace: "pre-wrap" }}>{value}</div>
                {cite ? <div style={{ marginTop: 4, color: "#64748b", fontSize: 12 }}>{cite}</div> : null}
              </div>
            );
          })}
        </div>
        {Array.isArray(payload?.red_flags) && payload.red_flags.length ? (
          <div style={{ marginTop: 12, color: "#991b1b" }}>紅旗：{payload.red_flags.join("；")}</div>
        ) : null}
      </div>
    </BlockSectionShell>
  );
}
