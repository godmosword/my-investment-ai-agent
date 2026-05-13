import { useState } from "react";
import { useQsrecStats, useExecutionIntents, useAnalysisBundle } from "../../../hooks/useApi";

function directionColor(dir) {
  const d = String(dir ?? "").toUpperCase();
  if (d === "LONG") return "var(--green, #22c55e)";
  if (d === "SHORT") return "var(--red, #ef4444)";
  return "var(--muted)";
}

function DeepDivePanel({ bundle }) {
  const [open, setOpen] = useState(false);
  if (!bundle?.snapshot) return null;
  const snap = bundle.snapshot;
  const recs = snap.recommendations ?? [];
  const priceSeries = snap.price_series ?? [];
  const lastClose = priceSeries.length > 0 ? priceSeries[priceSeries.length - 1].close : null;

  return (
    <div data-testid="deep-dive-panel" className="mb-4 rounded border border-[color:var(--border)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left text-[13px] font-semibold text-white/80 hover:bg-white/5"
        aria-expanded={open}
      >
        <span>Deep Dive — {bundle.symbol}</span>
        <span className="text-[11px] text-[var(--muted)]">{open ? "▲ 收合" : "▼ 展開"}</span>
      </button>

      {open ? (
        <div className="border-t border-[color:var(--border)] px-3 py-3">
          <div className="mb-3 flex flex-wrap gap-4 text-[12px]">
            <div>
              <span className="text-[var(--muted)]">來源：</span>
              <span className="text-white/80">{snap.source ?? "—"}</span>
            </div>
            <div>
              <span className="text-[var(--muted)]">截至：</span>
              <span className="text-white/80">{snap.as_of ? String(snap.as_of).slice(0, 10) : "—"}</span>
            </div>
            {lastClose != null ? (
              <div>
                <span className="text-[var(--muted)]">最近收盤：</span>
                <span className="font-mono text-white/90">{lastClose.toFixed(2)}</span>
              </div>
            ) : null}
            <div>
              <span className="text-[var(--muted)]">歷史點數：</span>
              <span className="text-white/80">{priceSeries.length}</span>
            </div>
          </div>

          {recs.length > 0 ? (
            <>
              <div className="mb-1.5 text-[11px] uppercase tracking-wide text-[var(--muted)]">
                推薦列（近 {recs.length} 筆）
              </div>
              <div className="overflow-x-auto rounded border border-[color:var(--border)]">
                <table className="w-full min-w-[360px] text-left text-[12px]">
                  <thead className="bg-[var(--panel)] text-[10px] uppercase text-[var(--muted)]">
                    <tr>
                      <th className="px-2 py-1.5">日期</th>
                      <th className="px-2 py-1.5">方向</th>
                      <th className="px-2 py-1.5">評分</th>
                      <th className="px-2 py-1.5">摘要</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recs.slice(0, 10).map((rec, idx) => (
                      <tr key={rec.signal_id ?? idx} className="border-t border-[color:var(--border)]">
                        <td className="px-2 py-1.5 font-mono text-[11px]">{rec.report_date ?? "—"}</td>
                        <td className="px-2 py-1.5 font-semibold" style={{ color: directionColor(rec.direction) }}>
                          {rec.direction ?? "—"}
                        </td>
                        <td className="px-2 py-1.5">{rec.star_rating != null ? "★".repeat(Math.min(rec.star_rating, 5)) : "—"}</td>
                        <td className="px-2 py-1.5 text-[var(--muted)]">{rec.thesis_one_liner ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-[12px] text-[var(--muted)]">無推薦紀錄。</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

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
  const [bundleSymbol, setBundleSymbol] = useState("NVDA");
  const { data: qsrec, isLoading: qLoading, error: qError } = useQsrecStats(7);
  const { data: intents = [], isLoading: iLoading, error: iError } = useExecutionIntents(100, {
    livePoll: false,
  });
  const {
    data: bundle,
    isLoading: bLoading,
    error: bError,
  } = useAnalysisBundle(bundleSymbol, 30, 12);

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

      <div className="card" style={{ marginBottom: 12 }} data-testid="analysis-m6-bundle">
        <div className="card-title">分析 bundle（M6）</div>
        <div className="page-subtitle" style={{ marginBottom: 8 }}>
          <code>/api/analysis/{"{symbol}"}</code> — quote + 可選 snapshot（失敗時 <code>snapshot_error</code>）。
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 8 }}>
          <span style={{ color: "var(--muted)" }}>代碼</span>
          <select
            value={bundleSymbol}
            onChange={(e) => setBundleSymbol(e.target.value)}
            style={{ padding: "4px 8px", borderRadius: 4, background: "var(--panel)", color: "var(--text)", border: "1px solid var(--border)" }}
          >
            {WATCHLIST.map(({ symbol }) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        {bLoading && <div className="loading" style={{ padding: "8px 0", fontSize: 12 }}>載入 bundle…</div>}
        {bError && !bLoading && (
          <div className="error-msg" style={{ fontSize: 12 }}>
            無法載入分析：<code>{bError.message}</code>
          </div>
        )}
        {!bLoading && !bError && bundle && (
          <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
            <div>
              <b style={{ color: "var(--text)" }}>{bundle.symbol}</b>
              {bundle.quote != null ? (
                <>
                  {" "}
                  · last：<b style={{ color: "var(--text)" }}>{JSON.stringify(bundle.quote?.last ?? bundle.quote)}</b>
                </>
              ) : null}
            </div>
            {bundle.snapshot_error ? (
              <div style={{ marginTop: 6, color: "var(--red, #f87171)" }}>
                snapshot：<code>{String(bundle.snapshot_error)}</code>
              </div>
            ) : bundle.snapshot ? (
              <div style={{ marginTop: 6 }}>snapshot：已載入（<code>{String(bundle.snapshot?.source ?? "ok")}</code>）</div>
            ) : (
              <div style={{ marginTop: 6 }}>snapshot：<span style={{ opacity: 0.75 }}>無</span></div>
            )}
          </div>
        )}
      </div>

      {/* Deep Dive collapsible panel (Q32) */}
      {!bLoading && !bError && bundle ? <DeepDivePanel bundle={bundle} /> : null}

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
        完整分析請見 <code>/insights</code> 投資觀點或 Telegram 戰報。
      </div>
    </>
  );
}
