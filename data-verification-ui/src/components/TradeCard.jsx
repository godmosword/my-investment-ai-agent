import { useState } from "react";

function fmt(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function Stars({ n }) {
  if (n == null) return null;
  return <span className="stars">{"★".repeat(n)}{"☆".repeat(Math.max(0, 4 - n))}</span>;
}

function StatusBadge({ status }) {
  if (!status) return null;
  const key = status.toLowerCase();
  return <span className={`status-badge status-${key}`}>{status.replace("_", " ")}</span>;
}

// ── Scorecard dimension bars ─────────────────────────────────────────────────
const SCORE_DIMS = [
  { key: "catalyst_score",  label: "催化" },
  { key: "flow_score",      label: "資金" },
  { key: "technical_score", label: "技術" },
  { key: "risk_fit_score",  label: "風控" },
  { key: "execution_score", label: "執行" },
];

function ScoreBar({ label, value }) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 70 ? "var(--green)" : pct >= 45 ? "var(--yellow)" : "var(--red)";
  return (
    <div style={{ marginBottom: 5 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)", marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ color }}>{Math.round(pct)}</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2, transition: "width 0.4s" }} />
      </div>
    </div>
  );
}

function Scorecard({ trade }) {
  const hasDims = SCORE_DIMS.some(({ key }) => trade[key] != null);
  if (!hasDims && trade.selection_score == null) return null;

  return (
    <div style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 6 }}>
      {trade.selection_score != null && (
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>選股總分</span>
          <span style={{ fontWeight: 700, color: "var(--accent)" }}>
            {Math.round(trade.selection_score)}/100
            {trade.score_gap != null && (
              <span style={{ color: "var(--muted)", fontWeight: 400, marginLeft: 4 }}>
                (vs次佳 +{Math.round(trade.score_gap)})
              </span>
            )}
          </span>
        </div>
      )}
      {hasDims && (
        <div>
          {SCORE_DIMS.map(({ key, label }) => (
            <ScoreBar key={key} label={label} value={trade[key]} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Three-scenario display ───────────────────────────────────────────────────
function Scenarios({ trade }) {
  const hasBull = !!trade.bull_scenario;
  const hasBase = !!trade.base_scenario;
  const hasBear = !!trade.bear_scenario;
  if (!hasBull && !hasBase && !hasBear) return null;

  return (
    <div style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 6 }}>
      <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
        情境分析
      </div>
      {hasBull && (
        <div style={{ fontSize: 11, marginBottom: 4, display: "flex", gap: 6 }}>
          <span>🐂</span>
          <span style={{ color: "var(--green)", lineHeight: 1.4 }}>{trade.bull_scenario}</span>
        </div>
      )}
      {hasBase && (
        <div style={{ fontSize: 11, marginBottom: 4, display: "flex", gap: 6 }}>
          <span>⚖️</span>
          <span style={{ color: "var(--text)", lineHeight: 1.4 }}>{trade.base_scenario}</span>
        </div>
      )}
      {hasBear && (
        <div style={{ fontSize: 11, marginBottom: 4, display: "flex", gap: 6 }}>
          <span>🐻</span>
          <span style={{ color: "var(--red)", lineHeight: 1.4 }}>{trade.bear_scenario}</span>
        </div>
      )}
    </div>
  );
}

// ── Main TradeCard ────────────────────────────────────────────────────────────
export default function TradeCard({ trade }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = trade.direction?.toUpperCase() === "LONG";
  const pnlColor = trade.pnl_pct > 0 ? "delta-up" : trade.pnl_pct < 0 ? "delta-down" : "delta-flat";
  const hasScorecard = SCORE_DIMS.some(({ key }) => trade[key] != null) || trade.selection_score != null;
  const hasScenarios = !!(trade.bull_scenario || trade.base_scenario || trade.bear_scenario);

  return (
    <div className="trade-card">
      {/* Header */}
      <div className="trade-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="trade-asset">{trade.asset}</span>
          <span className={`trade-direction direction-${isLong ? "long" : "short"}`}>
            {trade.direction}
          </span>
          {trade.category && (
            <span style={{ fontSize: 10, color: "var(--muted)" }}>{trade.category}</span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Stars n={trade.confidence} />
          <StatusBadge status={trade.status} />
        </div>
      </div>

      {/* Price row */}
      <div className="trade-prices">
        <div className="price-item">
          <span className="price-label">進場</span>
          <span className="price-value">{fmt(trade.entry_price)}</span>
        </div>
        <div className="price-item">
          <span className="price-label">目標</span>
          <span className="price-value" style={{ color: "var(--green)" }}>
            {fmt(trade.target_price)}
          </span>
        </div>
        <div className="price-item">
          <span className="price-label">停損</span>
          <span className="price-value" style={{ color: "var(--red)" }}>
            {fmt(trade.stop_price)}
          </span>
        </div>
      </div>

      {/* Meta row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, marginBottom: 4 }}>
        {trade.rr_ratio != null && (
          <span style={{ color: "var(--muted)" }}>
            R:R <strong style={{ color: "var(--text)" }}>{trade.rr_ratio}</strong>
          </span>
        )}
        {trade.timeframe && (
          <span style={{ color: "var(--muted)" }}>
            週期 <strong style={{ color: "var(--text)" }}>{trade.timeframe}</strong>
          </span>
        )}
        {trade.position_pct != null && (
          <span style={{ color: "var(--muted)" }}>
            倉位 <strong style={{ color: "var(--text)" }}>{trade.position_pct}%</strong>
          </span>
        )}
        {trade.pnl_pct != null && (
          <span>
            P&L <strong className={pnlColor}>{trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct}%</strong>
          </span>
        )}
      </div>

      {/* Narrative */}
      {trade.narrative && (
        <div className="trade-narrative">{trade.narrative}</div>
      )}

      {/* Expand toggle for scorecard + scenarios */}
      {(hasScorecard || hasScenarios) && (
        <button
          onClick={() => setExpanded(x => !x)}
          style={{
            width: "100%",
            background: "none",
            border: "none",
            borderTop: "1px solid var(--border)",
            color: "var(--muted)",
            fontSize: 11,
            cursor: "pointer",
            padding: "6px 0 0",
            marginTop: 8,
            textAlign: "center",
          }}
        >
          {expanded ? "▲ 收起" : "▼ 展開評分 & 情境分析"}
        </button>
      )}

      {expanded && (
        <>
          <Scorecard trade={trade} />
          <Scenarios trade={trade} />
        </>
      )}
    </div>
  );
}
