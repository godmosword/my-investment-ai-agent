import BlockSectionShell from "./BlockSectionShell";

/**
 * V2：`exec_summary` 專用呈現（結構化：命題 + 條列；legacy：`fallbackText`）。
 */
export default function ExecSummaryBlock({ anchor, title, headerExtras, payload }) {
  const p = payload && typeof payload === "object" ? payload : {};
  const oneLiner = typeof p.oneLiner === "string" ? p.oneLiner.trim() : "";
  const bullets = Array.isArray(p.bullets) ? p.bullets.map((x) => String(x ?? "").trim()).filter(Boolean) : [];
  const fallbackText = typeof p.fallbackText === "string" ? p.fallbackText.trim() : "";

  const hasStructured = Boolean(oneLiner || bullets.length);
  const hasLegacy = Boolean(fallbackText);

  if (!hasStructured && !hasLegacy) return null;

  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      {hasStructured ? (
        <div>
          {oneLiner ? (
            <div
              style={{
                borderLeft: "3px solid var(--accent)",
                background: "var(--surface)",
                borderRadius: "0 8px 8px 0",
                padding: "10px 12px",
                marginBottom: bullets.length ? 10 : 0,
                fontSize: 13,
                lineHeight: 1.6,
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", color: "var(--muted)" }}>
                投資命題
              </div>
              <p style={{ margin: "6px 0 0", color: "var(--text)" }}>{oneLiner}</p>
            </div>
          ) : null}
          {bullets.length > 0 ? (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {bullets.map((b, i) => (
                <li key={`${i}-${b.slice(0, 24)}`} className="summary-block" style={{ marginBottom: i === bullets.length - 1 ? 0 : undefined }}>
                  {b}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <div className="summary-block">{fallbackText}</div>
      )}
    </BlockSectionShell>
  );
}
