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

const SCORE_DIMS = [
  { key: "catalyst_score", label: "催化" },
  { key: "flow_score", label: "資金" },
  { key: "technical_score", label: "技術" },
  { key: "risk_fit_score", label: "風控" },
  { key: "execution_score", label: "執行" },
];

function ScoreBar({ label, value }) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 70 ? "var(--green)" : pct >= 45 ? "var(--yellow)" : "var(--red)";
  return (
    <div style={{ marginBottom: 5 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "var(--muted)",
          marginBottom: 2,
        }}
      >
        <span>{label}</span>
        <span style={{ color }}>{Math.round(pct)}</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: "var(--border)", overflow: "hidden" }}>
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 2,
          }}
        />
      </div>
    </div>
  );
}

function Scorecard({ trade, hasDims }) {
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

function Scenarios({ trade }) {
  const hasBull = !!trade.bull_scenario;
  const hasBase = !!trade.base_scenario;
  const hasBear = !!trade.bear_scenario;
  if (!hasBull && !hasBase && !hasBear) return null;

  return (
    <div style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 6 }}>
      <div
        style={{
          fontSize: 10,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 6,
        }}
      >
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

export default function TradeCard({ trade }) {
  const [tradeDetailsOpen, setTradeDetailsOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [decisionOpen, setDecisionOpen] = useState(false);

  const isLong = trade.direction?.toUpperCase() === "LONG";
  const pnlColor = trade.pnl_pct > 0 ? "delta-up" : trade.pnl_pct < 0 ? "delta-down" : "delta-flat";
  const hasDims = SCORE_DIMS.some(({ key }) => trade[key] != null);
  const hasScorecard = hasDims || trade.selection_score != null;
  const hasScenarios = !!(trade.bull_scenario || trade.base_scenario || trade.bear_scenario);
  const hasAiLogic = !!(trade.trigger || trade.invalidation || trade.narrative);

  return (
    <div className="trade-card">
      {/* Glassbox：預設僅標的、方向、部位、P&L、狀態 */}
      <div className="trade-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className="trade-asset">{trade.asset}</span>
          <span className={`trade-direction direction-${isLong ? "long" : "short"}`}>
            {trade.direction}
          </span>
          {trade.category && (
            <span style={{ fontSize: 10, color: "var(--muted)" }}>{trade.category}</span>
          )}
        </div>
        <StatusBadge status={trade.status} />
      </div>

      <div className="trade-compact-row">
        {trade.position_pct != null && (
          <span style={{ color: "var(--muted)" }}>
            部位 <strong style={{ color: "var(--text)" }}>{trade.position_pct}%</strong>
          </span>
        )}
        {trade.pnl_pct != null && (
          <span style={{ color: "var(--muted)" }}>
            當前 P&amp;L{" "}
            <strong className={pnlColor}>
              {trade.pnl_pct > 0 ? "+" : ""}
              {trade.pnl_pct}%
            </strong>
          </span>
        )}
        {trade.position_pct == null && trade.pnl_pct == null && (
          <span style={{ color: "var(--muted)", fontSize: 11 }}>尚無部位／損益欄位</span>
        )}
      </div>

      <button
        type="button"
        className="trade-accordion-btn trade-accordion-btn--ghost"
        onClick={() => setTradeDetailsOpen((x) => !x)}
        aria-expanded={tradeDetailsOpen}
      >
        {tradeDetailsOpen ? "▲ 收起交易細節（價格／週期）" : "▼ 展開交易細節（價格／週期）"}
      </button>

      {tradeDetailsOpen && (
        <>
          <div className="trade-prices" style={{ marginTop: 10 }}>
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
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, marginBottom: 4 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Stars n={trade.confidence} />
            </span>
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
          </div>
        </>
      )}

      {hasAiLogic && (
        <button
          type="button"
          className="trade-accordion-btn"
          onClick={() => setDecisionOpen((x) => !x)}
          aria-expanded={decisionOpen}
        >
          {decisionOpen ? "▲ 收起決策邏輯" : "▼ 展開決策邏輯（觸發／失效／敘事）"}
        </button>
      )}

      {decisionOpen && hasAiLogic && (
        <div
          style={{
            marginTop: 10,
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "rgba(255,255,255,.02)",
          }}
        >
          {trade.trigger && (
            <div style={{ marginBottom: 10 }}>
              <div
                style={{
                  fontSize: 10,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 4,
                }}
              >
                觸發條件（Trigger）
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.45, color: "var(--text)" }}>{trade.trigger}</div>
            </div>
          )}
          {trade.invalidation && (
            <div style={{ marginBottom: 10 }}>
              <div
                style={{
                  fontSize: 10,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 4,
                }}
              >
                失效條件（Invalidation）
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.45, color: "var(--text)" }}>{trade.invalidation}</div>
            </div>
          )}
          {trade.narrative && (
            <div>
              <div
                style={{
                  fontSize: 10,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: 6,
                }}
              >
                敘事邏輯（Narrative）
              </div>
              <blockquote
                className="trade-narrative"
                style={{
                  margin: 0,
                  padding: "10px 12px",
                  borderLeft: "3px solid var(--accent)",
                  background: "rgba(0,212,170,.08)",
                  borderRadius: "0 8px 8px 0",
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: "var(--text)",
                }}
              >
                {trade.narrative}
              </blockquote>
            </div>
          )}
        </div>
      )}

      {(hasScorecard || hasScenarios) && (
        <button
          type="button"
          className="trade-accordion-btn trade-accordion-btn--ghost"
          onClick={() => setScoreOpen((x) => !x)}
          aria-expanded={scoreOpen}
        >
          {scoreOpen ? "▲ 收起評分與情境" : "▼ 展開評分與情境分析"}
        </button>
      )}

      {scoreOpen && (
        <>
          <Scorecard trade={trade} hasDims={hasDims} />
          <Scenarios trade={trade} />
        </>
      )}
    </div>
  );
}
