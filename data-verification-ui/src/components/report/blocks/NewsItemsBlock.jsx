import BlockSectionShell from "./BlockSectionShell";

export default function NewsItemsBlock({ anchor, title, headerExtras, payload }) {
  const items = Array.isArray(payload) ? payload : [];
  const shellTitle = `${title} (${items.length})`;
  return (
    <BlockSectionShell id={anchor} title={shellTitle} headerExtras={headerExtras}>
      {items.map((n, i) => (
        <div key={i} className="card" style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>
            {n.timestamp_line} · #{n.index}
          </div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{n.title}</div>
          <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 6 }}>{n.source_and_nature}</div>
          <div style={{ fontSize: 13, lineHeight: 1.45 }}>{n.summary}</div>
          <div style={{ fontSize: 13, marginTop: 8, color: "rgb(167 243 208)" }}>{n.investment_takeaway}</div>
          <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted)" }}>
            編輯共識：{n.editor_consensus}
            {n.pricing_note ? ` · 定價：${n.pricing_note}` : ""}
          </div>
        </div>
      ))}
    </BlockSectionShell>
  );
}
