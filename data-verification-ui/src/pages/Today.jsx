import { useMetricsLatest, useReport } from "../hooks/useApi";
import MetricCard from "../components/MetricCard";
import TradeCard from "../components/TradeCard";

function regimeInfo(score) {
  if (score == null) return { label: "— 未知", cls: "regime-neutral" };
  if (score >= 3.5) return { label: "🔴 Risk OFF", cls: "regime-off" };
  if (score >= 2.5) return { label: "🟡 中性", cls: "regime-neutral" };
  return { label: "🟢 Risk ON", cls: "regime-on" };
}

export default function Today() {
  const today = new Date().toISOString().slice(0, 10);
  const { data: metrics, isLoading: mLoading, error: mError } = useMetricsLatest();
  const { data: report, isLoading: rLoading } = useReport(today);

  if (mLoading) return <div className="loading">載入中…</div>;
  if (mError) return <div className="error-msg">無法連線至 API：{mError.message}</div>;

  const regime = regimeInfo(metrics?.avg_risk_score);
  const ts = metrics?.timestamp
    ? new Date(metrics.timestamp).toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <>
      <div className="page-header">
        <div className="page-title">今日戰情室</div>
        {ts && <div className="page-subtitle">更新：{ts}</div>}
      </div>

      <span className={`regime-badge ${regime.cls}`}>{regime.label}</span>

      <div className="metrics-grid">
        <MetricCard
          label="ICE DXY"
          value={metrics?.dxy}
          delta={metrics?.delta_dxy}
          format={(v) => v.toFixed(2)}
        />
        <MetricCard
          label="ETF 資金流"
          value={metrics?.etf_flow_millions}
          delta={metrics?.delta_etf_flow_millions}
          unit="億"
          format={(v) => (v > 0 ? `+${v}` : `${v}`)}
        />
        <MetricCard
          label="MVRV Z-Score"
          value={metrics?.mvrv_z_score}
          delta={metrics?.delta_mvrv_z_score}
          format={(v) => v.toFixed(2)}
        />
        <MetricCard
          label="風險評分"
          value={metrics?.avg_risk_score}
          delta={metrics?.delta_avg_risk_score}
          unit="/5"
          format={(v) => `${v.toFixed(1)}`}
        />
      </div>

      {metrics?.grok_summary && (
        <>
          <div className="section-header">🔮 幣圈情報（Grok）</div>
          <div className="summary-block">{metrics.grok_summary}</div>
        </>
      )}

      {metrics?.gpt_summary && (
        <>
          <div className="section-header">🤖 AI 產業情報</div>
          <div className="summary-block">{metrics.gpt_summary}</div>
        </>
      )}

      {!rLoading && report?.recommendations?.length > 0 && (
        <>
          <div className="section-header">💼 今日建議（QSREC）</div>
          {report.recommendations.map((t, i) => (
            <TradeCard key={i} trade={t} />
          ))}
        </>
      )}
    </>
  );
}
