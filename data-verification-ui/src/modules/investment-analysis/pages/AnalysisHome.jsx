import { useQsrecStats, useExecutionIntents } from "../../../hooks/useApi";

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

function QsrecKpi({ label, value, color }) {
  return (
    <div className="card" style={{ textAlign: "center", flex: 1, minWidth: 100 }}>
      <div className="metric-label" style={{ fontSize: 11, color: "var(--muted)" }}>{label}</div>
      <div className="metric-value" style={{ color: color ?? "var(--text)", fontSize: 26, marginTop: 4 }}>
        {value}
      </div>
    </div>
  );
}

function WatchlistTable({ intents }) {
  const intentMap = {};
  for (const r of intents ?? []) {
    const asset = String(r.asset ?? "").trim().toUpperCase();
    if (asset && !intentMap[asset]) intentMap[asset] = r;
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
  const { data: qsrec, isLoading: qLoading, error: qError } = useQsrecStats(7);
  const { data: intents = [], isLoading: iLoading, error: iError } = useExecutionIntents(100, {
    livePoll: false,
  });

  const passRateColor =
    !qsrec ? "var(--text)"
    : qsrec.pass_rate_pct >= 70 ? "var(--green)"
    : qsrec.pass_rate_pct >= 40 ? "#fbbf24"
    : "var(--red)";

  return (
    <>
      <div className="page-header">
        <div className="page-title">投資分析</div>
        <div className="page-subtitle">觀察名單 · 模型品質（源自 QSREC reviewer_log）</div>
      </div>

      {/* Model Quality — real QSREC stats */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="card-title">模型品質（近 7 日）</div>
        {qLoading && <div className="loading" style={{ padding: "12px 0" }}>載入 QSREC 數據中…</div>}
        {qError && !qLoading && (
          <div className="error-msg" style={{ marginBottom: 8 }}>
            無法載入 QSREC 數據：<code>{qError.message}</code>
          </div>
        )}
        {!qLoading && !qError && !qsrec?.total_days && (
          <div className="page-subtitle" style={{ opacity: 0.75 }}>
            Reviewer loop 尚未啟動 — 無 QSREC 數據。
          </div>
        )}
        {!qLoading && !qError && !!qsrec?.total_days && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <QsrecKpi
              label="通過率"
              value={`${qsrec.pass_rate_pct}%`}
              color={passRateColor}
            />
            <QsrecKpi
              label="平均交易數"
              value={qsrec.avg_trade_count}
              color="var(--text)"
            />
            <QsrecKpi
              label="降級天數"
              value={qsrec.degraded_count}
              color={qsrec.degraded_count > 0 ? "var(--red)" : "var(--green)"}
            />
            <QsrecKpi
              label="已審天數"
              value={`${qsrec.total_days}d`}
              color="var(--muted)"
            />
          </div>
        )}
      </div>

      {/* Watchlist */}
      <div className="section-header">📋 觀察名單（QSREC 宇宙）</div>
      <div className="card" style={{ padding: "8px 0" }}>
        {iLoading && <div className="loading" style={{ padding: "12px 16px" }}>載入意圖中…</div>}
        {iError && !iLoading && (
          <div className="error-msg" style={{ padding: "12px 16px" }}>
            無法載入意圖：<code>{iError.message}</code>
          </div>
        )}
        {!iLoading && !iError && <WatchlistTable intents={intents} />}
      </div>

      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 8, opacity: 0.65 }}>
        完整分析請見 <code>/briefs</code> 日報終端或 Telegram 戰報。
      </div>
    </>
  );
}
