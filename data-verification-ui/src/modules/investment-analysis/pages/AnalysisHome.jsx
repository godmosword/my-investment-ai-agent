import { useMetricsLatest, useExecutionIntents } from "../../../hooks/useApi";

const WATCHLIST = [
  { symbol: "NVDA",  name: "Nvidia",    sector: "AI 半導體" },
  { symbol: "MSFT",  name: "Microsoft", sector: "雲端 / AI" },
  { symbol: "GOOGL", name: "Alphabet",  sector: "雲端 / 搜尋" },
  { symbol: "META",  name: "Meta",      sector: "社群 / AI" },
  { symbol: "AAPL",  name: "Apple",     sector: "消費電子" },
  { symbol: "ORCL",  name: "Oracle",    sector: "企業軟體" },
  { symbol: "BTC",   name: "Bitcoin",   sector: "數位資產" },
  { symbol: "ETH",   name: "Ethereum",  sector: "智能合約" },
];

const SCORE_DIMS = [
  { key: "tech",  label: "技術面", color: "#2ee6be" },
  { key: "fund",  label: "基本面", color: "#8b5cf6" },
  { key: "sent",  label: "情緒面", color: "#fbbf24" },
];

function RadarBar({ label, pct, color }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)", marginBottom: 3 }}>
        <span>{label}</span>
        <span style={{ color }}>{Math.round(pct)}%</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

function deriveScores(metrics) {
  if (!metrics) return { tech: 50, fund: 50, sent: 50 };
  const sentRaw = metrics.sentiment_score ?? 0;
  const riskRaw = metrics.avg_risk_score ?? 2.5;
  const sopr = metrics.sopr ?? 1;
  const tech = Math.max(10, Math.min(95, 100 - (riskRaw / 5) * 100));
  const fund = Math.max(10, Math.min(95, (sopr - 0.85) / 0.4 * 100));
  const sent = Math.max(10, Math.min(95, 50 + sentRaw * 30));
  return { tech: Math.round(tech), fund: Math.round(fund), sent: Math.round(sent) };
}

function WatchlistTable({ intents }) {
  const intentMap = {};
  for (const r of intents ?? []) {
    if (r.asset) intentMap[r.asset.toUpperCase()] = r;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted)" }}>
            <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 600 }}>代碼</th>
            <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 600 }}>板塊</th>
            <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 600 }}>最新意圖</th>
            <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 600 }}>狀態</th>
          </tr>
        </thead>
        <tbody>
          {WATCHLIST.map(({ symbol, name, sector }) => {
            const intent = intentMap[symbol];
            const dirColor =
              intent?.direction?.toUpperCase() === "LONG"
                ? "var(--green)"
                : intent?.direction?.toUpperCase() === "SHORT"
                  ? "var(--red)"
                  : "var(--muted)";
            return (
              <tr
                key={symbol}
                style={{ borderTop: "1px solid var(--border)", transition: "background 0.15s" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.02)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "")}
              >
                <td style={{ padding: "10px 8px" }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{symbol}</div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>{name}</div>
                </td>
                <td style={{ padding: "10px 8px", fontSize: 11, color: "var(--muted)" }}>{sector}</td>
                <td style={{ padding: "10px 8px" }}>
                  {intent ? (
                    <span style={{ fontWeight: 600, color: dirColor, fontSize: 12 }}>
                      {intent.direction}
                    </span>
                  ) : (
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>—</span>
                  )}
                </td>
                <td style={{ padding: "10px 8px" }}>
                  {intent ? (
                    <span
                      style={{
                        fontSize: 10,
                        padding: "2px 7px",
                        borderRadius: 4,
                        background:
                          intent.status === "APPROVED_FOR_PAPER"
                            ? "rgba(52,211,153,0.15)"
                            : "rgba(120,160,200,0.1)",
                        color:
                          intent.status === "APPROVED_FOR_PAPER"
                            ? "var(--green)"
                            : "var(--muted)",
                      }}
                    >
                      {intent.status ?? "—"}
                    </span>
                  ) : (
                    <span style={{ fontSize: 10, color: "var(--muted)", opacity: 0.5 }}>無意圖</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function AnalysisHome() {
  const { data: metrics, isLoading: mLoading } = useMetricsLatest();
  const { data: intents = [], isLoading: iLoading } = useExecutionIntents(100, { livePoll: false });
  const scores = deriveScores(metrics);

  return (
    <div className="page-content" style={{ padding: "16px 16px 80px" }}>
      <div className="page-header">
        <div className="page-title">投資分析</div>
        <div className="page-subtitle">觀察名單 · 多空維度評分（源自 BigQuery daily_metrics）</div>
      </div>

      {/* Dimension score bars */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-title">市場多空維度（即時）</div>
        {mLoading ? (
          <div style={{ fontSize: 12, color: "var(--muted)" }}>載入中…</div>
        ) : (
          SCORE_DIMS.map(({ key, label, color }) => (
            <RadarBar key={key} label={label} pct={scores[key]} color={color} />
          ))
        )}
        <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 8, opacity: 0.6 }}>
          ※ 技術面由風險評分換算；基本面由 SOPR 換算；情緒面由 sentiment_score 換算。
        </div>
      </div>

      {/* Watchlist */}
      <div className="section-header">📋 觀察名單（QSREC 宇宙）</div>
      <div className="card" style={{ padding: "8px 0" }}>
        {iLoading ? (
          <div style={{ padding: "12px 16px", fontSize: 12, color: "var(--muted)" }}>載入意圖中…</div>
        ) : (
          <WatchlistTable intents={intents} />
        )}
      </div>

      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 8, opacity: 0.65 }}>
        完整分析請見 <code>/briefs</code> 日報終端或 Telegram 戰報。
      </div>
    </div>
  );
}
