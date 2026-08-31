import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useExecutionIntents,
  useGateStatus,
  useReports,
  useQuantSignals,
  useQuantBacktest,
  useSymbolQuote,
} from "../../../hooks/useApi";
import { DEFAULT_GATE_STATUS } from "../../../constants/gateDisplay";
import { finiteNumber, paperEntry, paperExit, isPaperClosedRow, calcStats } from "../../../utils/positionStats";
import OfflineBanner from "../../../components/OfflineBanner";

const GATE_BADGE = {
  pass:     { label: "通過",  bg: "rgba(52,211,153,0.15)", color: "var(--green)" },
  fail:     { label: "需修正", bg: "rgba(251,191,36,0.15)",  color: "#fbbf24" },
  degraded: { label: "降級",  bg: "rgba(239,68,68,0.15)",   color: "var(--red)" },
  [DEFAULT_GATE_STATUS]: { label: "未審",  bg: "rgba(120,160,200,0.1)",  color: "var(--muted)" },
};

function GateBadge({ status }) {
  const cfg = GATE_BADGE[status] ?? GATE_BADGE[DEFAULT_GATE_STATUS];
  return (
    <span
      style={{
        fontSize: 11,
        padding: "2px 8px",
        borderRadius: 4,
        background: cfg.bg,
        color: cfg.color,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {cfg.label}
    </span>
  );
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div className="card" style={{ textAlign: "center" }}>
      <div className="metric-label">{label}</div>
      <div
        className="metric-value"
        style={{ color: color ?? "var(--text)", fontSize: 28, marginTop: 4 }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    PENDING_REVIEW: { label: "待審", color: "var(--muted)" },
    APPROVED_FOR_PAPER: { label: "紙上運行", color: "var(--accent)" },
    REJECTED: { label: "已駁回", color: "var(--red)" },
    PAPER_SUBMITTED: { label: "紙上提交", color: "var(--accent)" },
    PAPER_FILLED: { label: "紙上成交", color: "var(--green)" },
    PAPER_CLOSED: { label: "紙上結算", color: "var(--muted)" },
    EXITED: { label: "已出場", color: "var(--yellow)" },
    CLOSED: { label: "已關閉", color: "var(--muted)" },
    SUPERSEDED: { label: "已取代", color: "var(--muted)" },
  };
  const info = map[status] ?? { label: status ?? "—", color: "var(--muted)" };
  return (
    <span
      style={{
        fontSize: 10,
        padding: "2px 7px",
        borderRadius: 4,
        background: `${info.color}22`,
        color: info.color,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {info.label}
    </span>
  );
}

function isActiveIntent(r) {
  const s = String(r.status ?? "").toUpperCase();
  if (s === "REJECTED" || s === "SUPERSEDED") return false;
  if (isPaperClosedRow(r)) return false;
  return true;
}

const BACKTEST_SYMBOLS = ["BTC", "SPY", "NVDA", "MSFT", "AAPL"];

function isRealQuantSignal(signal) {
  if (!signal || typeof signal !== "object") return false;
  if (String(signal.id || "") === "placeholder-neutral") return false;
  return Boolean(String(signal.symbol || signal.asset || "").trim());
}

function realQuantSignals(payload) {
  if (!payload || payload.source === "placeholder") return [];
  return (payload.signals ?? []).filter(isRealQuantSignal);
}

function formatQuote(value) {
  if (!finiteNumber(value)) return "—";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: Math.abs(Number(value)) >= 100 ? 2 : 4,
  });
}

function IntradaySignalRow({ signal }) {
  const navigate = useNavigate();
  const symbol = String(signal.symbol || signal.asset || "").trim().toUpperCase();
  const quote = useSymbolQuote(symbol, { livePoll: true });
  if (!symbol) return null;
  return (
    <button
      type="button"
      className="grid min-h-[52px] w-full grid-cols-[minmax(70px,0.8fr)_minmax(90px,1fr)_minmax(86px,0.8fr)] items-center gap-2 rounded border border-white/10 bg-black/15 px-3 py-2 text-left text-[12px] hover:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-cyan-400/50"
      data-testid="quant-intraday-row"
      data-symbol={symbol}
      onClick={() => navigate(`/insights?symbol=${encodeURIComponent(symbol)}`)}
    >
      <span>
        <span className="block font-mono text-[14px] font-semibold text-white">{symbol}</span>
        <span className="block text-[10px] uppercase text-[var(--muted)]">{signal.direction || "neutral"}</span>
      </span>
      <span>
        <span className="block text-white/80">{signal.status || "—"}</span>
        <span className="block truncate text-[11px] text-[var(--muted)]">{signal.label || signal.id || "—"}</span>
      </span>
      <span className="text-right">
        <span className="block font-mono text-white" data-testid="quant-intraday-price">
          {quote.isLoading ? "…" : quote.isError ? "—" : formatQuote(quote.data?.last)}
        </span>
        <span className="block text-[10px] text-[var(--muted)]">{quote.data?.source || "quote"}</span>
      </span>
    </button>
  );
}

function IntradayMonitor({ signals = [], isLoading, error }) {
  const [filter, setFilter] = useState("");
  const filtered = signals
    .filter((signal) => String(signal.symbol || signal.asset || "").trim())
    .filter((signal) => {
      const q = filter.trim().toUpperCase();
      if (!q) return true;
      const haystack = `${signal.symbol || signal.asset || ""} ${signal.status || ""} ${signal.label || ""}`.toUpperCase();
      return haystack.includes(q);
    })
    .slice(0, 12);

  return (
    <section data-testid="quant-intraday-monitor" className="mb-4 rounded border border-[color:var(--border)] p-3">
      <OfflineBanner testId="quant-intraday-offline-banner" />
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[13px] font-semibold text-white/85">Intraday Monitor</div>
          <div className="text-[11px] text-[var(--muted)]">Paper signals + existing quote polling · no new feed</div>
        </div>
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter symbol/status"
          className="min-h-[44px] rounded border border-white/15 bg-black/35 px-3 text-[12px] text-white placeholder:text-white/35"
          data-testid="quant-intraday-filter"
        />
      </div>
      {isLoading ? (
        <div className="text-[12px] text-[var(--muted)]" data-testid="quant-intraday-loading">
          載入訊號…
        </div>
      ) : null}
      {error ? (
        <div className="text-[12px] text-amber-300" data-testid="quant-intraday-error">
          無法載入：{error.message}
        </div>
      ) : null}
      {!isLoading && !error && signals.length === 0 ? (
        <div
          className="text-[12px] text-[var(--muted)]"
          data-testid="quant-intraday-empty"
          role="status"
        >
          UNKNOWN：尚無真實訊號
        </div>
      ) : null}
      <div className="grid gap-2">
        {filtered.map((signal) => (
          <IntradaySignalRow key={signal.id || signal.symbol || signal.asset} signal={signal} />
        ))}
      </div>
    </section>
  );
}

function BacktestPanel() {
  const [sym, setSym] = useState("BTC");
  const { data, isLoading, error, refetch } = useQuantBacktest(sym);

  const curve = data?.equity_curve ?? [];
  const maxVal = curve.length > 0 ? Math.max(...curve.map((p) => p.value)) : 10000;
  const minVal = curve.length > 0 ? Math.min(...curve.map((p) => p.value)) : 9000;
  const range = maxVal - minVal || 1;

  return (
    <div data-testid="backtest-panel" className="mb-4 rounded border border-[color:var(--border)] p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold text-white/80">Backtest（paper-derived）</span>
        <select
          value={sym}
          onChange={(e) => setSym(e.target.value)}
          className="rounded border border-white/15 bg-black/40 px-2 py-0.5 text-[12px] text-white"
        >
          {BACKTEST_SYMBOLS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <span className="text-[11px] text-[var(--muted)]">紙上教育用，不承諾收益</span>
      </div>

      {isLoading && <div className="text-[12px] text-[var(--muted)]">計算中…</div>}
      {error && (
        <div className="text-[12px] text-[var(--muted)]">
          {error.message.startsWith("404") ? "Backtest 已停用（QUANT_BACKTEST_ENABLED 未設定）" : `錯誤：${error.message}`}
        </div>
      )}
      {!isLoading && !error && data && (
        <>
          <div className="mb-2 flex flex-wrap gap-4 text-[12px]">
            <span className="text-[var(--muted)]">總報酬：<b style={{ color: data.total_return >= 0 ? "var(--green)" : "var(--red)" }}>{data.total_return >= 0 ? "+" : ""}{(data.total_return * 100).toFixed(1)}%</b></span>
            <span className="text-[var(--muted)]">最大回撤：<b style={{ color: "var(--red)" }}>{(data.max_drawdown * 100).toFixed(1)}%</b></span>
            <span className="text-[var(--muted)]">Sharpe：<b className="text-white/80">{data.sharpe}</b></span>
            {data.trade_count != null ? (
              <span className="text-[var(--muted)]">Trades：<b className="text-white/80">{data.trade_count}</b></span>
            ) : null}
          </div>
          {/* SVG sparkline equity curve */}
          {curve.length > 1 ? (
            <svg viewBox={`0 0 ${curve.length * 10} 60`} className="w-full" style={{ height: 60 }}>
              <polyline
                points={curve.map((p, i) => `${i * 10},${60 - ((p.value - minVal) / range) * 55}`).join(" ")}
                fill="none"
                stroke={data.total_return >= 0 ? "#22c55e" : "#ef4444"}
                strokeWidth="2"
              />
            </svg>
          ) : null}
        </>
      )}
    </div>
  );
}

export default function QuantHome() {
  const { data: rows = [], isLoading, error } = useExecutionIntents(200, {
    livePoll: false,
    statusFilter: "all",
    categoryFilter: "all",
    sortBy: "updated_desc",
  });

  const { data: quantPayload, isLoading: qSigLoading, error: qSigError } = useQuantSignals();
  const realSignals = realQuantSignals(quantPayload);

  const { data: reports } = useReports(3);
  const dates = reports?.map((r) => r.report_date) ?? [];
  // Fixed 3 calls — never conditional, satisfies React hook rules
  const gs0 = useGateStatus(dates[0]);
  const gs1 = useGateStatus(dates[1]);
  const gs2 = useGateStatus(dates[2]);
  const gateEntries = [
    dates[0] && { date: dates[0], ...gs0.data },
    dates[1] && { date: dates[1], ...gs1.data },
    dates[2] && { date: dates[2], ...gs2.data },
  ].filter(Boolean);

  const stats = calcStats(rows);
  const active = rows.filter(isActiveIntent);

  return (
    <>
      <div className="page-header">
        <div className="page-title">量化交易</div>
        <div className="page-subtitle">紙上模擬績效（execution_intents · 僅追蹤，不下單）</div>
      </div>

      {/* Backtest panel (Q33) */}
      <BacktestPanel />

      <IntradayMonitor
        signals={realSignals}
        isLoading={qSigLoading}
        error={qSigError}
      />

      {/* QSREC gate-status — last 3 days */}
      <div className="card" style={{ marginBottom: 12 }} data-testid="quant-m7-signals">
        <div className="card-title">量化訊號（M7）</div>
        <div className="page-subtitle" style={{ marginBottom: 8, opacity: 0.85 }}>
          <code>/api/quant/signals</code> — 教育／紙上敘事用，不承諾收益、不自動下單。
        </div>
        {qSigLoading && (
          <div className="loading" style={{ padding: "6px 0", fontSize: 12 }} data-testid="quant-m7-loading">
            載入訊號…
          </div>
        )}
        {qSigError && !qSigLoading && (
          <div className="error-msg" style={{ fontSize: 12 }} data-testid="quant-m7-error">
            無法載入訊號：<code>{qSigError.message}</code>
          </div>
        )}
        {!qSigLoading && !qSigError && realSignals.length > 0 ? (
          <ul data-testid="quant-m7-list" style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--muted)" }}>
            {realSignals.slice(0, 8).map((s) => (
              <li key={s.id ?? JSON.stringify(s)} style={{ marginBottom: 4 }}>
                <span style={{ color: "var(--text)", fontWeight: 600 }}>{s.label ?? s.id}</span>
                {s.direction != null ? (
                  <span style={{ marginLeft: 6, opacity: 0.85 }}>({String(s.direction)})</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
        {!qSigLoading && !qSigError && realSignals.length === 0 ? (
          <div
            className="page-subtitle"
            style={{ opacity: 0.85 }}
            data-testid="quant-m7-empty"
            role="status"
          >
            UNKNOWN：尚無真實訊號
          </div>
        ) : null}
      </div>

      <div className="card" style={{ marginBottom: 12 }} data-testid="quant-qsrec-gate-panel">
        <div className="card-title">QSREC 近 3 日審核結果</div>
        {gateEntries.length === 0 && (
          <div className="page-subtitle" style={{ opacity: 0.75 }}>
            Reviewer loop 尚未啟動 — 無審核紀錄。
          </div>
        )}
        {gateEntries.map(({ date, gate_status }) => (
          <div
            key={date}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "6px 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ fontSize: 13, color: "var(--muted)" }}>{date}</span>
            <GateBadge status={gate_status ?? DEFAULT_GATE_STATUS} />
          </div>
        ))}
      </div>

      {isLoading && <div className="loading" style={{ padding: "20px 0" }}>載入中…</div>}
      {error && (
        <div className="error-msg">
          無法載入意圖紀錄：<code>{error.message}</code>
        </div>
      )}

      {/* KPI grid */}
      {stats ? (
        <>
          <div className="section-header subtle">績效概覽（已結算信號）</div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
              gap: 10,
              marginBottom: 16,
            }}
          >
            <KpiCard label="勝率" value={`${stats.winRate}%`} sub={`${stats.wins}/${stats.total}`} color="var(--green)" />
            <KpiCard label="平均盈虧" value={`${stats.avgPnl}%`} color={Number(stats.avgPnl) >= 0 ? "var(--green)" : "var(--red)"} />
            <KpiCard label="盈虧比 R:R" value={stats.rr} sub="avg win / avg loss" color="var(--accent)" />
            <KpiCard label="總信號數" value={stats.total} color="var(--text)" />
          </div>
        </>
      ) : !isLoading && !error ? (
        <div className="card" style={{ marginBottom: 12, color: "var(--muted)", fontSize: 13 }}>
          尚無已結算信號可計算績效。
        </div>
      ) : null}

      {/* Active signals */}
      <div className="section-header subtle">運行中信號（{active.length}）</div>
      {active.length === 0 && !isLoading && (
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>目前無運行中信號。</div>
      )}
      {active.slice(0, 20).map((r) => (
        <div key={r.signal_id} className="card" style={{ marginBottom: 8, padding: "12px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div>
              <span style={{ fontWeight: 700, fontSize: 15 }}>{r.asset ?? "—"}</span>
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  fontWeight: 600,
                  color:
                    (r.direction ?? "").toUpperCase() === "LONG"
                      ? "var(--green)"
                      : "var(--red)",
                }}
              >
                {r.direction ?? "—"}
              </span>
            </div>
            <StatusPill status={r.status} />
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 8,
              fontSize: 12,
            }}
          >
            {[
              { l: "進場", v: paperEntry(r) },
              { l: "出場", v: paperExit(r) ?? "—" },
              { l: "類別", v: r.category ?? "—" },
            ].map(({ l, v }) => (
              <div key={l}>
                <div style={{ color: "var(--muted)", fontSize: 10, marginBottom: 2 }}>{l}</div>
                <div style={{ fontWeight: 600 }}>{v ?? "—"}</div>
              </div>
            ))}
          </div>
          {(r.thesis_one_liner || r.thesis) && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 8, lineHeight: 1.45 }}>
              {r.thesis_one_liner ?? r.thesis}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
