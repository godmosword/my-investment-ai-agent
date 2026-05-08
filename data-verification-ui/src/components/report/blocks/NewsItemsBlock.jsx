import BlockSectionShell from "./BlockSectionShell";

const URGENCY_LEVELS = {
  critical: { label: "緊急", color: "var(--red)",    bg: "rgba(248,113,113,0.1)",  border: "rgba(248,113,113,0.3)" },
  high:     { label: "高",   color: "var(--yellow)", bg: "rgba(251,191,36,0.08)", border: "rgba(251,191,36,0.25)" },
  medium:   { label: "中",   color: "var(--accent)", bg: "rgba(46,230,190,0.06)",  border: "rgba(46,230,190,0.2)" },
  low:      { label: "低",   color: "var(--muted)",  bg: undefined,                border: undefined },
};

function urgencyInfo(urgency) {
  const key = (urgency ?? "").toLowerCase();
  return URGENCY_LEVELS[key] ?? URGENCY_LEVELS.low;
}

function UrgencyBadge({ urgency }) {
  if (!urgency) return null;
  const info = urgencyInfo(urgency);
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 700,
        padding: "1px 6px",
        borderRadius: 3,
        border: `1px solid ${info.border ?? "var(--border)"}`,
        color: info.color,
        background: info.bg ?? "transparent",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        flexShrink: 0,
      }}
    >
      {info.label}
    </span>
  );
}

export default function NewsItemsBlock({ anchor, title, headerExtras, payload }) {
  const items = Array.isArray(payload) ? payload : [];
  const shellTitle = `${title} (${items.length})`;
  return (
    <BlockSectionShell id={anchor} title={shellTitle} headerExtras={headerExtras}>
      {items.map((n, i) => {
        const info = urgencyInfo(n.urgency);
        return (
          <div
            key={i}
            className="card"
            style={{
              marginBottom: 10,
              borderColor: info.border ?? "var(--border)",
              background: info.bg
                ? `linear-gradient(135deg, ${info.bg} 0%, rgba(18,26,42,0.95) 100%)`
                : undefined,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 6,
                gap: 8,
              }}
            >
              <div style={{ fontSize: 11, color: "var(--muted)" }}>
                {n.timestamp_line} · #{n.index}
              </div>
              <UrgencyBadge urgency={n.urgency} />
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
        );
      })}
    </BlockSectionShell>
  );
}
