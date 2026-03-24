import { useState } from "react";
import { useTrades, useTradesPerformance } from "../hooks/useApi";
import TradeCard from "../components/TradeCard";

const STATUS_TABS = [
  { key: null,         label: "全部" },
  { key: "OPEN",       label: "持倉中" },
  { key: "HIT_TARGET", label: "達標" },
  { key: "HIT_STOP",   label: "停損" },
];

function PerfStats({ days }) {
  const { data: perf, isLoading } = useTradesPerformance(days);
  if (isLoading || !perf) return null;

  const winColor = (perf.win_rate_pct ?? 0) >= 50 ? "var(--green)" : "var(--red)";

  return (
    <>
      <div className="perf-grid">
        <div className="perf-stat">
          <div className="perf-value" style={{ color: winColor }}>
            {perf.win_rate_pct != null ? `${perf.win_rate_pct}%` : "—"}
          </div>
          <div className="perf-label">勝率</div>
        </div>
        <div className="perf-stat">
          <div className="perf-value">
            {perf.avg_rr != null ? perf.avg_rr : "—"}
          </div>
          <div className="perf-label">平均 R:R</div>
        </div>
        <div className="perf-stat">
          <div
            className="perf-value"
            style={{ color: (perf.avg_pnl_pct ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}
          >
            {perf.avg_pnl_pct != null ? `${perf.avg_pnl_pct > 0 ? "+" : ""}${perf.avg_pnl_pct}%` : "—"}
          </div>
          <div className="perf-label">平均 P&L</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
        <span>總計 <strong style={{ color: "var(--text)" }}>{perf.total}</strong></span>
        <span>獲利 <strong style={{ color: "var(--green)" }}>{perf.wins}</strong></span>
        <span>停損 <strong style={{ color: "var(--red)" }}>{perf.losses}</strong></span>
        <span>到期 <strong>{perf.expired}</strong></span>
        <span>持倉中 <strong style={{ color: "#a5b4fc" }}>{perf.open_count}</strong></span>
      </div>
    </>
  );
}

export default function Trades() {
  const [activeStatus, setActiveStatus] = useState(null);
  const [days, setDays] = useState(60);
  const { data: trades, isLoading, error } = useTrades(activeStatus, days);

  return (
    <>
      <div className="page-header">
        <div className="page-title">交易建議</div>
      </div>

      <PerfStats days={90} />

      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={String(key)}
            onClick={() => setActiveStatus(key)}
            style={{
              padding: "5px 12px",
              borderRadius: 6,
              border: "1px solid",
              borderColor: activeStatus === key ? "var(--accent)" : "var(--border)",
              background: activeStatus === key ? "rgba(0,212,170,.12)" : "transparent",
              color: activeStatus === key ? "var(--accent)" : "var(--muted)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          {[30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              style={{
                padding: "5px 10px",
                borderRadius: 6,
                border: "1px solid",
                borderColor: days === d ? "var(--accent2)" : "var(--border)",
                background: days === d ? "rgba(99,102,241,.12)" : "transparent",
                color: days === d ? "#a5b4fc" : "var(--muted)",
                fontSize: 11,
                cursor: "pointer",
              }}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {isLoading && <div className="loading">載入中…</div>}
      {error     && <div className="error-msg">載入失敗：{error.message}</div>}

      {!isLoading && trades?.length === 0 && (
        <div className="loading">此篩選條件下無紀錄</div>
      )}

      {trades?.map((t, i) => (
        <div key={i}>
          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
            {t.report_date}
          </div>
          <TradeCard trade={t} />
        </div>
      ))}
    </>
  );
}
