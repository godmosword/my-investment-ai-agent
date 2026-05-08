import { useState } from "react";

function fmt(v) {
  if (v == null || v === "") return "N/A";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function safeStr(v) {
  if (v == null) return "N/A";
  const s = String(v).trim();
  return s === "" ? "N/A" : s;
}

function parsePrice(v) {
  if (v == null) return null;
  const n = parseFloat(String(v).replace(/[^0-9.-]/g, ""));
  return Number.isNaN(n) ? null : n;
}

function ConfidenceStars({ n }) {
  if (n == null || n === "" || Number.isNaN(Number(n))) return <span>N/A</span>;
  const c = Math.min(4, Math.max(0, Math.floor(Number(n))));
  if (c <= 0) return <span>N/A</span>;
  return <span style={{ color: "var(--yellow)", letterSpacing: "-0.04em" }}>{"★".repeat(c)}{"☆".repeat(4 - c)}</span>;
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
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)", marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ color }}>{Math.round(pct)}</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

/** Horizontal price bar: stop ←—entry—→ target */
function PriceRangeBar({ entry, target, stop, direction }) {
  const e = parsePrice(entry);
  const t = parsePrice(target);
  const s = parsePrice(stop);
  if (e == null || t == null || s == null) return null;

  const lo = Math.min(e, t, s);
  const hi = Math.max(e, t, s);
  const range = hi - lo;
  if (range <= 0) return null;

  const pct = (v) => `${(((v - lo) / range) * 100).toFixed(1)}%`;
  const isLong = (direction || "").toUpperCase() !== "SHORT";
  const gainColor = isLong ? "var(--green)" : "var(--red)";
  const lossColor = isLong ? "var(--red)" : "var(--green)";

  const entryPct = parseFloat(pct(e));
  const targetPct = parseFloat(pct(t));
  const stopPct = parseFloat(pct(s));

  const gainLeft = isLong ? entryPct : targetPct;
  const gainWidth = Math.abs(targetPct - entryPct);
  const lossLeft = isLong ? stopPct : entryPct;
  const lossWidth = Math.abs(entryPct - stopPct);

  return (
    <div style={{ margin: "12px 0 6px" }}>
      <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 4, letterSpacing: "0.04em", textTransform: "uppercase" }}>
        Price Range
      </div>
      <div style={{ position: "relative", height: 8, borderRadius: 4, background: "var(--border)", overflow: "hidden" }}>
        {/* loss zone */}
        <div style={{ position: "absolute", top: 0, left: `${lossLeft}%`, width: `${lossWidth}%`, height: "100%", background: lossColor, opacity: 0.35 }} />
        {/* gain zone */}
        <div style={{ position: "absolute", top: 0, left: `${gainLeft}%`, width: `${gainWidth}%`, height: "100%", background: gainColor, opacity: 0.5 }} />
        {/* entry marker */}
        <div style={{ position: "absolute", top: -2, left: `calc(${entryPct}% - 1px)`, width: 2, height: 12, background: "var(--text)", borderRadius: 1 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--muted)", marginTop: 3 }}>
        <span style={{ color: lossColor }}>STOP {fmt(s)}</span>
        <span style={{ color: "var(--text)", fontWeight: 600 }}>ENTRY {fmt(e)}</span>
        <span style={{ color: gainColor }}>TARGET {fmt(t)}</span>
      </div>
    </div>
  );
}

function Scorecard({ trade, hasDims }) {
  if (!hasDims && trade.selection_score == null) return null;
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
      {trade.selection_score != null && (
        <div style={{ marginBottom: 8, display: "flex", justifyContent: "space-between", fontSize: 11 }}>
          <span style={{ color: "var(--muted)" }}>選股總分</span>
          <span style={{ fontWeight: 700, color: "var(--accent)", fontFamily: "'JetBrains Mono', monospace" }}>
            {Math.round(trade.selection_score)}/100
            {trade.score_gap != null && (
              <span style={{ marginLeft: 4, fontWeight: 400, color: "var(--muted)" }}>
                (vs次佳 +{Math.round(trade.score_gap)})
              </span>
            )}
          </span>
        </div>
      )}
      {hasDims && SCORE_DIMS.map(({ key, label }) => (
        <ScoreBar key={key} label={label} value={trade[key]} />
      ))}
    </div>
  );
}

function Scenarios({ trade }) {
  const hasBull = !!trade.bull_scenario;
  const hasBase = !!trade.base_scenario;
  const hasBear = !!trade.bear_scenario;
  if (!hasBull && !hasBase && !hasBear) return null;
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
      <div style={{ marginBottom: 6, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted)" }}>情境分析</div>
      {hasBull && (
        <div style={{ marginBottom: 4, display: "flex", gap: 6, fontSize: 11 }}>
          <span>▲</span>
          <span style={{ color: "var(--green)", lineHeight: 1.4 }}>{trade.bull_scenario}</span>
        </div>
      )}
      {hasBase && (
        <div style={{ marginBottom: 4, display: "flex", gap: 6, fontSize: 11 }}>
          <span>—</span>
          <span style={{ color: "var(--text)", lineHeight: 1.4 }}>{trade.base_scenario}</span>
        </div>
      )}
      {hasBear && (
        <div style={{ display: "flex", gap: 6, fontSize: 11 }}>
          <span>▼</span>
          <span style={{ color: "var(--red)", lineHeight: 1.4 }}>{trade.bear_scenario}</span>
        </div>
      )}
    </div>
  );
}

function directionStyle(dir) {
  const u = (dir || "").toUpperCase();
  if (u === "LONG") return { background: "rgba(5,150,105,0.08)", color: "var(--green)", border: "1px solid rgba(5,150,105,0.2)" };
  if (u === "SHORT") return { background: "rgba(220,38,38,0.08)", color: "var(--red)", border: "1px solid rgba(220,38,38,0.2)" };
  return { background: "rgba(0,0,0,0.05)", color: "var(--muted)", border: "1px solid var(--border)" };
}

export default function TradeCard({ trade: tradeProp }) {
  const trade = tradeProp ?? {};
  const [isExpanded, setIsExpanded] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);

  const pnlColor = trade.pnl_pct > 0 ? "var(--green)" : trade.pnl_pct < 0 ? "var(--red)" : "var(--muted)";
  const hasDims = SCORE_DIMS.some(({ key }) => trade[key] != null);
  const hasScorecard = hasDims || trade.selection_score != null;
  const hasScenarios = !!(trade.bull_scenario || trade.base_scenario || trade.bear_scenario);
  const assetLabel = trade.asset != null && String(trade.asset).trim() !== "" ? trade.asset : "N/A";

  return (
    <div
      className="card"
      style={{ marginBottom: 12, padding: "16px 18px" }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {assetLabel}
          </span>
          <span style={{ fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 4, ...directionStyle(trade.direction) }}>
            {trade.direction || "N/A"}
          </span>
          {trade.category && (
            <span style={{ fontSize: 10, color: "var(--muted)" }}>{trade.category}</span>
          )}
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div><ConfidenceStars n={trade.confidence} /></div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
            部位 {trade.position_pct != null && trade.position_pct !== "" ? `${trade.position_pct}%` : "N/A"}
          </div>
        </div>
      </div>

      {/* Status / P&L */}
      {(trade.status || trade.pnl_pct != null) && (
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginTop: 6, fontSize: 11, color: "var(--muted)" }}>
          <StatusBadge status={trade.status} />
          {trade.pnl_pct != null && (
            <span>當前 P&amp;L <strong style={{ color: pnlColor }}>{trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct}%</strong></span>
          )}
        </div>
      )}

      {/* Price grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, margin: "14px 0 4px" }}>
        {[
          { label: "進場 · Entry", value: trade.entry_price },
          { label: "目標 · Target", value: trade.target_price },
          { label: "停損 · Stop", value: trade.stop_price },
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", marginBottom: 3 }}>{label}</div>
            <div style={{ fontSize: 15, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: "var(--text)" }}>{fmt(value)}</div>
          </div>
        ))}
      </div>

      {/* R:R price range bar */}
      <PriceRangeBar
        entry={trade.entry_price}
        target={trade.target_price}
        stop={trade.stop_price}
        direction={trade.direction}
      />

      {/* R:R / timeframe / risk stats */}
      {(trade.rr_ratio != null || trade.timeframe || trade.max_drawdown_pct || trade.expected_win_rate || trade.signal_score) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 11, color: "var(--muted)", margin: "6px 0 2px" }}>
          {trade.rr_ratio != null && <span>R:R <strong style={{ color: "var(--text)", fontFamily: "'JetBrains Mono', monospace" }}>{trade.rr_ratio}</strong></span>}
          {trade.max_drawdown_pct && <span>Max DD <strong style={{ color: "var(--red)", fontFamily: "'JetBrains Mono', monospace" }}>{trade.max_drawdown_pct}</strong></span>}
          {trade.expected_win_rate && <span>Win <strong style={{ color: "var(--green)", fontFamily: "'JetBrains Mono', monospace" }}>{trade.expected_win_rate}</strong></span>}
          {trade.signal_score && <span>Signal <strong style={{ color: "var(--accent)", fontFamily: "'JetBrains Mono', monospace" }}>{trade.signal_score}</strong></span>}
          {trade.timeframe && <span>週期 <strong style={{ color: "var(--text)" }}>{trade.timeframe}</strong></span>}
        </div>
      )}

      {/* Expand button: AI decision logic */}
      <button
        type="button"
        style={{ width: "100%", textAlign: "center", fontSize: 12, color: "var(--accent)", padding: "8px 0", marginTop: 10, background: "transparent", cursor: "pointer", border: "none", borderTop: "1px solid var(--border)" }}
        onClick={() => setIsExpanded((x) => !x)}
        aria-expanded={isExpanded}
      >
        {isExpanded ? "收起 ↑" : "展開 AI 決策邏輯 ↓"}
      </button>

      {isExpanded && (
        <div style={{ background: "rgba(0,0,0,0.03)", borderRadius: 8, padding: "14px 16px", marginTop: 8, display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--yellow)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>觸發條件（Trigger）</div>
            <p style={{ color: "var(--text)", lineHeight: 1.5, margin: 0, whiteSpace: "pre-wrap" }}>{safeStr(trade.trigger)}</p>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--red)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>失效條件（Invalidation）</div>
            <p style={{ color: "var(--text)", lineHeight: 1.5, margin: 0, whiteSpace: "pre-wrap" }}>{safeStr(trade.invalidation)}</p>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent2)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>敘事邏輯（Narrative）</div>
            <p style={{ color: "var(--text)", lineHeight: 1.5, margin: 0, whiteSpace: "pre-wrap" }}>{safeStr(trade.narrative)}</p>
          </div>
        </div>
      )}

      {(hasScorecard || hasScenarios) && (
        <button
          type="button"
          style={{ width: "100%", textAlign: "center", fontSize: 12, color: "var(--muted)", padding: "6px 0", marginTop: 6, background: "transparent", cursor: "pointer", border: "none", borderTop: "1px solid var(--border)" }}
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
