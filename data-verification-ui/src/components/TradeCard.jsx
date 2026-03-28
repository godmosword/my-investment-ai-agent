import { useState } from "react";

/** 價格／數值：缺漏時 N/A */
function fmt(v) {
  if (v == null || v === "") return "N/A";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

/** 觸發／失效／敘事等字串 */
function safeStr(v) {
  if (v == null) return "N/A";
  const s = String(v).trim();
  return s === "" ? "N/A" : s;
}

function ConfidenceStars({ n }) {
  if (n == null || n === "" || Number.isNaN(Number(n))) {
    return <span>N/A</span>;
  }
  const c = Math.min(4, Math.max(0, Math.floor(Number(n))));
  if (c <= 0) return <span>N/A</span>;
  return <span className="text-yellow-400 tracking-tight">{"⭐".repeat(c)}</span>;
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
    <div className="mt-3 border-t border-gray-800 pt-3">
      {trade.selection_score != null && (
        <div className="mb-2 flex justify-between text-[11px]">
          <span className="text-gray-500">選股總分</span>
          <span className="font-bold text-teal-400">
            {Math.round(trade.selection_score)}/100
            {trade.score_gap != null && (
              <span className="ml-1 font-normal text-gray-500">(vs次佳 +{Math.round(trade.score_gap)})</span>
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
    <div className="mt-3 border-t border-gray-800 pt-3">
      <div className="mb-2 text-[10px] uppercase tracking-wider text-gray-500">情境分析</div>
      {hasBull && (
        <div className="mb-1 flex gap-2 text-[11px]">
          <span>🐂</span>
          <span className="leading-snug text-emerald-400">{trade.bull_scenario}</span>
        </div>
      )}
      {hasBase && (
        <div className="mb-1 flex gap-2 text-[11px]">
          <span>⚖️</span>
          <span className="leading-snug text-gray-200">{trade.base_scenario}</span>
        </div>
      )}
      {hasBear && (
        <div className="mb-1 flex gap-2 text-[11px]">
          <span>🐻</span>
          <span className="leading-snug text-red-400">{trade.bear_scenario}</span>
        </div>
      )}
    </div>
  );
}

function directionBadgeClass(dir) {
  const u = (dir || "").toUpperCase();
  if (u === "LONG") return "bg-green-900/50 text-green-400 text-sm px-2 py-1 rounded font-medium";
  if (u === "SHORT") return "bg-red-900/50 text-red-400 text-sm px-2 py-1 rounded font-medium";
  return "bg-gray-800/50 text-gray-300 text-sm px-2 py-1 rounded font-medium";
}

export default function TradeCard({ trade: tradeProp }) {
  const trade = tradeProp ?? {};
  const [isExpanded, setIsExpanded] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);

  const pnlColor =
    trade.pnl_pct > 0 ? "text-emerald-400" : trade.pnl_pct < 0 ? "text-red-400" : "text-gray-400";
  const hasDims = SCORE_DIMS.some(({ key }) => trade[key] != null);
  const hasScorecard = hasDims || trade.selection_score != null;
  const hasScenarios = !!(trade.bull_scenario || trade.base_scenario || trade.bear_scenario);

  const assetLabel = trade.asset != null && String(trade.asset).trim() !== "" ? trade.asset : "N/A";

  return (
    <div
      className="mb-3 bg-gray-900 bg-opacity-60 backdrop-blur-md border border-gray-700 rounded-xl p-5 shadow-lg hover:border-gray-500 transition-colors"
    >
      {/* Header */}
      <div className="flex justify-between items-center gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <span className="text-xl font-bold text-white truncate">{assetLabel}</span>
          <span className={directionBadgeClass(trade.direction)}>
            {trade.direction != null && String(trade.direction).trim() !== ""
              ? trade.direction
              : "N/A"}
          </span>
          {trade.category && (
            <span className="text-[10px] text-gray-500 shrink-0">{trade.category}</span>
          )}
        </div>
        <div className="text-right text-gray-400 text-sm shrink-0 space-y-0.5">
          <div className="flex justify-end">
            <ConfidenceStars n={trade.confidence} />
          </div>
          <div>
            部位{" "}
            {trade.position_pct != null && trade.position_pct !== ""
              ? `${trade.position_pct}%`
              : "N/A"}
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <StatusBadge status={trade.status} />
        {trade.pnl_pct != null && (
          <span>
            當前 P&amp;L{" "}
            <strong className={pnlColor}>
              {trade.pnl_pct > 0 ? "+" : ""}
              {trade.pnl_pct}%
            </strong>
          </span>
        )}
      </div>

      {/* Price grid */}
      <div className="grid grid-cols-3 gap-4 my-4">
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">進場 · Entry</div>
          <div className="text-lg font-mono text-gray-100">{fmt(trade.entry_price)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">目標 · Target</div>
          <div className="text-lg font-mono text-gray-100">{fmt(trade.target_price)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">停損 · Stop</div>
          <div className="text-lg font-mono text-gray-100">{fmt(trade.stop_price)}</div>
        </div>
      </div>

      {(trade.rr_ratio != null || trade.timeframe) && (
        <div className="flex flex-wrap gap-3 text-[11px] text-gray-500 mb-1">
          {trade.rr_ratio != null && (
            <span>
              R:R <strong className="text-gray-200">{trade.rr_ratio}</strong>
            </span>
          )}
          {trade.timeframe && (
            <span>
              週期 <strong className="text-gray-200">{trade.timeframe}</strong>
            </span>
          )}
        </div>
      )}

      {/* AI 決策邏輯 accordion */}
      <button
        type="button"
        className="w-full text-center text-sm text-blue-400 hover:text-blue-300 py-2 border-t border-gray-800 mt-2 bg-transparent cursor-pointer"
        onClick={() => setIsExpanded((x) => !x)}
        aria-expanded={isExpanded}
      >
        {isExpanded ? "收起 ↑" : "展開 AI 決策邏輯 ↓"}
      </button>

      {isExpanded && (
        <div className="bg-gray-800/50 rounded-lg p-4 mt-2 space-y-3 text-sm">
          <div>
            <div className="text-xs font-semibold text-amber-400 mb-1">觸發條件（Trigger）</div>
            <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">{safeStr(trade.trigger)}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-red-400 mb-1">失效條件（Invalidation）</div>
            <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">{safeStr(trade.invalidation)}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-blue-400 mb-1">敘事邏輯（Narrative）</div>
            <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">{safeStr(trade.narrative)}</p>
          </div>
        </div>
      )}

      {(hasScorecard || hasScenarios) && (
        <button
          type="button"
          className="w-full text-center text-sm text-gray-400 hover:text-gray-300 py-2 border-t border-gray-800 mt-2 bg-transparent cursor-pointer"
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
