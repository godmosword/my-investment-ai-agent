import { useMetricsLatest, useReport, useOpenPositions } from "../hooks/useApi";
import MetricCard from "../components/MetricCard";
import TradeCard from "../components/TradeCard";
import { regimeInfo } from "../utils/regime";

export default function Today() {
  const today = new Date().toISOString().slice(0, 10);
  const { data: metrics, isLoading: mLoading, error: mError } = useMetricsLatest();
  const { data: report, isLoading: rLoading } = useReport(today);
  const { data: openPos, isLoading: oLoading, error: oError } = useOpenPositions(90);

  const longCount =
    openPos?.filter((t) => t.direction?.toUpperCase() === "LONG").length ?? 0;
  const shortCount =
    openPos?.filter((t) => t.direction?.toUpperCase() === "SHORT").length ?? 0;

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

      <div className="section-header subtle">鏈上情緒（與 daily_metrics / Streamlit 同源）</div>
      <div className="metrics-grid">
        <MetricCard
          label="SOPR"
          value={metrics?.sopr}
          delta={metrics?.delta_sopr}
          format={(v) => v.toFixed(4)}
        />
        <MetricCard
          label="情緒分數"
          value={metrics?.sentiment_score}
          delta={metrics?.delta_sentiment_score}
          format={(v) => v.toFixed(3)}
        />
        <MetricCard
          label="交易所淨流向"
          value={metrics?.exchange_netflow}
          delta={metrics?.delta_exchange_netflow}
          format={(v) => v.toFixed(2)}
        />
        <MetricCard
          label="Regime score"
          value={metrics?.regime_score}
          delta={metrics?.delta_regime_score}
          format={(v) => v.toFixed(2)}
        />
      </div>
      <p className="page-subtitle" style={{ marginTop: "-0.5rem", opacity: 0.75 }}>
        BTC 資金費率為工具層即時查詢，請見 Streamlit 戰情室「資金費率」摺疊區或當日 Telegram 戰報。
      </p>

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

      <div className="section-header">部位健康度（Portfolio Health）</div>
      {oLoading && <div className="loading">載入運行中部位…</div>}
      {oError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          無法載入部位：{oError.message}
        </div>
      )}
      {!oLoading && !oError && Array.isArray(openPos) && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            marginBottom: 18,
            alignItems: "center",
          }}
        >
          <span
            className="trade-direction direction-long"
            style={{ fontSize: 13, padding: "6px 14px", borderRadius: 8 }}
          >
            多單 {longCount} 筆
          </span>
          <span
            className="trade-direction direction-short"
            style={{ fontSize: 13, padding: "6px 14px", borderRadius: 8 }}
          >
            空單 {shortCount} 筆
          </span>
          {longCount === 0 && shortCount === 0 && (
            <span style={{ fontSize: 12, color: "var(--muted)" }}>目前無運行中部位</span>
          )}
        </div>
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
