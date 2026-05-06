import BlockSectionShell from "./BlockSectionShell";

function citationText(item) {
  const first = Array.isArray(item?.citations) ? item.citations[0] : null;
  if (!first) return "";
  return [first.section, first.excerpt].filter(Boolean).join(" · ");
}

export default function AgencyResearchBlock({ anchor, title, headerExtras, payload }) {
  const deliverables = Array.isArray(payload?.deliverables) ? payload.deliverables : [];

  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="summary-block">
        {payload?.ticker ? <div style={{ marginBottom: 10, fontWeight: 700 }}>{payload.ticker}</div> : null}
        <div style={{ display: "grid", gap: 10 }}>
          {deliverables.map((item, idx) => {
            const cite = citationText(item);
            return (
              <div key={`${item?.name || "deliverable"}-${idx}`}>
                <div style={{ fontWeight: 700 }}>
                  {item?.name}
                  {item?.confidence ? <span style={{ color: "#64748b" }}> · {item.confidence}</span> : null}
                </div>
                <div style={{ whiteSpace: "pre-wrap" }}>{item?.content}</div>
                {cite ? <div style={{ marginTop: 4, color: "#64748b", fontSize: 12 }}>{cite}</div> : null}
              </div>
            );
          })}
        </div>
        {Array.isArray(payload?.risk_register) && payload.risk_register.length ? (
          <div style={{ marginTop: 12 }}>風險登錄：{payload.risk_register.join("；")}</div>
        ) : null}
      </div>
    </BlockSectionShell>
  );
}
