import BlockSectionShell from "./BlockSectionShell";

function regimeBorderColor(regimeKey) {
  const k = String(regimeKey ?? "").toLowerCase();
  if (k === "risk_on") return "rgba(52, 211, 153, 0.55)";
  if (k === "risk_off") return "rgba(248, 113, 113, 0.45)";
  if (k === "neutral") return "rgba(251, 191, 36, 0.45)";
  return "var(--border)";
}

function regimeLabel(regimeKey) {
  const k = String(regimeKey ?? "").toLowerCase();
  if (k === "risk_on") return "Risk-on";
  if (k === "risk_off") return "Risk-off";
  if (k === "neutral") return "Neutral";
  return regimeKey ? String(regimeKey) : "";
}

/**
 * V2：`market_mode` 專用呈現（結構化：體制／敘事／評分卡；legacy：`fallbackText`）。
 */
export default function MarketModeBlock({ anchor, title, headerExtras, payload }) {
  const p = payload && typeof payload === "object" ? payload : {};
  const regimeKey = typeof p.regimeKey === "string" ? p.regimeKey : "";
  const regimeLabelText = typeof p.regimeLabel === "string" ? p.regimeLabel.trim() : "";
  const narrative = typeof p.narrative === "string" ? p.narrative.trim() : "";
  const scoreSuffix = typeof p.scoreSuffix === "string" ? p.scoreSuffix.trim() : "";
  const scoreLines = Array.isArray(p.scoreLines)
    ? p.scoreLines.map((x) => String(x ?? "").trim()).filter(Boolean)
    : [];
  const fallbackText = typeof p.fallbackText === "string" ? p.fallbackText.trim() : "";

  const displayRegime = regimeLabelText || regimeLabel(regimeKey);
  const showRegimePill = Boolean(regimeKey || regimeLabelText);
  const showHeaderRow = showRegimePill || Boolean(scoreSuffix);
  const hasStructured = Boolean(regimeKey || regimeLabelText || narrative || scoreSuffix || scoreLines.length);
  const hasLegacy = Boolean(fallbackText);

  if (!hasStructured && !hasLegacy) return null;

  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      {hasStructured ? (
        <div>
          {showHeaderRow ? (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 10,
                marginBottom: narrative ? 12 : scoreLines.length ? 12 : 0,
              }}
            >
              {showRegimePill ? (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 12px",
                    borderRadius: 999,
                    fontSize: 12,
                    fontWeight: 600,
                    border: `1px solid ${regimeBorderColor(regimeKey)}`,
                    background: "rgba(255,255,255,0.03)",
                    color: "var(--text)",
                  }}
                >
                  {displayRegime || regimeLabel(regimeKey)}
                </span>
              ) : null}
              {scoreSuffix ? (
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{scoreSuffix}</span>
              ) : null}
            </div>
          ) : null}
          {narrative ? (
            <div className="summary-block" style={{ marginBottom: scoreLines.length ? 10 : 0 }}>
              {narrative}
            </div>
          ) : null}
          {scoreLines.length > 0 ? (
            <div className="summary-block">
              {scoreLines.map((line, i) => (
                <div key={`${i}-${line.slice(0, 16)}`} style={{ marginBottom: i === scoreLines.length - 1 ? 0 : 6 }}>
                  {line}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="summary-block">{fallbackText}</div>
      )}
    </BlockSectionShell>
  );
}
