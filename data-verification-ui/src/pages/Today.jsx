import { useState } from "react";
import { useMetricsLatest, useReport, useOpenPositions, useWarRoomLatest } from "../hooks/useApi";
import MetricCard from "../components/MetricCard";
import TradeCard from "../components/TradeCard";
import PositionHealthStrip from "../components/PositionHealthStrip";
import WarRoomCard from "../components/WarRoomCard";
import { regimeInfo } from "../utils/regime";
import {
  useGlassboxDemoMode,
  MOCK_METRICS_LATEST,
  MOCK_OPEN_POSITIONS,
  mockReportForDate,
} from "../utils/mockToday";

export default function Today() {
  const [warRoomIntentFilter, setWarRoomIntentFilter] = useState("all");
  const today = new Date().toISOString().slice(0, 10);
  const { data: metrics, isLoading: mLoading, error: mError } = useMetricsLatest();
  const { data: report, isLoading: rLoading, error: rError } = useReport(today);
  const { data: openPos, isLoading: oLoading, error: oError } = useOpenPositions(90);
  const { data: warRoom, isLoading: wLoading, error: wError } = useWarRoomLatest();

  const forceDemo = useGlassboxDemoMode();
  const allSettled = !mLoading && !rLoading && !oLoading;
  const apiAllFailed = allSettled && Boolean(mError && rError && oError);
  const useDemo = forceDemo || apiAllFailed;

  const effectiveMetrics = useDemo ? MOCK_METRICS_LATEST : mError ? null : metrics;
  const effectiveOpen = useDemo ? MOCK_OPEN_POSITIONS : oError ? null : openPos;
  const effectiveReport = useDemo ? mockReportForDate(today) : rError ? null : report;

  const openCount = Array.isArray(effectiveOpen) ? effectiveOpen.length : 0;
  const longCount =
    effectiveOpen?.filter((t) => t.direction?.toUpperCase() === "LONG").length ?? 0;
  const shortCount =
    effectiveOpen?.filter((t) => t.direction?.toUpperCase() === "SHORT").length ?? 0;

  const regime = regimeInfo(effectiveMetrics?.avg_risk_score);
  const ts = effectiveMetrics?.timestamp
    ? new Date(effectiveMetrics.timestamp).toLocaleString("zh-TW", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  const showMetricsBlock =
    useDemo || (!mLoading && !mError && metrics);
  const metricsLoadingUi = !useDemo && mLoading && !mError;

  return (
    <>
      <PositionHealthStrip
        openCount={openCount}
        loading={useDemo ? false : oLoading}
        error={useDemo ? null : oError}
      />

      {useDemo && (
        <div className="glassbox-demo-banner glassbox-demo-banner--today" role="status">
          {forceDemo ? (
            <>
              已啟用 <code>VITE_GLASSBOX_MOCK=1</code>：顯示<strong>示範戰情室資料</strong>（非 BigQuery 實盤）。
            </>
          ) : (
            <>
              後端 <code>/api/metrics/latest</code>、<code>/api/positions/open</code>、
              <code>/api/reports/…</code> 目前皆無法使用，已自動載入<strong>示範資料</strong>以便預覽 UI。
              請啟動 <code>uvicorn api:app</code> 並設定 <code>VITE_API_URL</code>（見專案 README）。
            </>
          )}
        </div>
      )}

      <div className="page-header">
        <div className="page-title">今日戰情室</div>
        {ts && <div className="page-subtitle">更新：{ts}</div>}
      </div>

      <div className="section-header subtle">War Room（Gate / Scratchpad / Intent）</div>
      <WarRoomCard
        warRoom={warRoom}
        loading={useDemo ? false : wLoading}
        error={useDemo ? null : wError}
        intentStatusFilter={warRoomIntentFilter}
        onIntentStatusChange={setWarRoomIntentFilter}
      />

      {!useDemo && mError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          無法載入最新指標（<code>/api/metrics/latest</code>）：{mError.message}
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.9 }}>
            請確認 FastAPI 已啟動、BigQuery 憑證就緒，並檢查 <code>VITE_API_URL</code>。
            若僅預覽 UI，可設 <code>VITE_GLASSBOX_MOCK=1</code>。
          </div>
        </div>
      )}

      {metricsLoadingUi && <div className="loading">載入指標中…</div>}

      {showMetricsBlock && effectiveMetrics && (
        <>
          <span className={`regime-badge ${regime.cls}`}>{regime.label}</span>

          <div className="metrics-grid">
            <MetricCard
              label="ICE DXY"
              value={effectiveMetrics?.dxy}
              delta={effectiveMetrics?.delta_dxy}
              format={(v) => v.toFixed(2)}
            />
            <MetricCard
              label="ETF 資金流"
              value={effectiveMetrics?.etf_flow_millions}
              delta={effectiveMetrics?.delta_etf_flow_millions}
              unit="億"
              format={(v) => (v > 0 ? `+${v}` : `${v}`)}
            />
            <MetricCard
              label="MVRV Z-Score"
              value={effectiveMetrics?.mvrv_z_score}
              delta={effectiveMetrics?.delta_mvrv_z_score}
              format={(v) => v.toFixed(2)}
            />
            <MetricCard
              label="風險評分"
              value={effectiveMetrics?.avg_risk_score}
              delta={effectiveMetrics?.delta_avg_risk_score}
              unit="/5"
              format={(v) => `${v.toFixed(1)}`}
            />
          </div>

          <div className="section-header subtle">鏈上情緒（與 daily_metrics / Streamlit 同源）</div>
          <div className="metrics-grid">
            <MetricCard
              label="SOPR"
              value={effectiveMetrics?.sopr}
              delta={effectiveMetrics?.delta_sopr}
              format={(v) => v.toFixed(4)}
            />
            <MetricCard
              label="情緒分數"
              value={effectiveMetrics?.sentiment_score}
              delta={effectiveMetrics?.delta_sentiment_score}
              format={(v) => v.toFixed(3)}
            />
            <MetricCard
              label="交易所淨流向"
              value={effectiveMetrics?.exchange_netflow}
              delta={effectiveMetrics?.delta_exchange_netflow}
              format={(v) => v.toFixed(2)}
            />
            <MetricCard
              label="Regime score"
              value={effectiveMetrics?.regime_score}
              delta={effectiveMetrics?.delta_regime_score}
              format={(v) => v.toFixed(2)}
            />
          </div>
          <p className="page-subtitle" style={{ marginTop: "-0.5rem", opacity: 0.75 }}>
            BTC 資金費率為工具層即時查詢，請見 Streamlit 戰情室「資金費率」摺疊區或當日 Telegram 戰報。
          </p>

          {effectiveMetrics?.grok_summary && (
            <>
              <div className="section-header">🔮 幣圈情報（Grok）</div>
              <div className="summary-block">{effectiveMetrics.grok_summary}</div>
            </>
          )}

          {effectiveMetrics?.gpt_summary && (
            <>
              <div className="section-header">🤖 AI 產業情報</div>
              <div className="summary-block">{effectiveMetrics.gpt_summary}</div>
            </>
          )}
        </>
      )}

      <div className="section-header subtle">多空結構（OPEN）</div>
      {(useDemo || (!oLoading && !oError)) && Array.isArray(effectiveOpen) && (
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

      {!useDemo && rError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          無法載入今日報告：{rError.message}
        </div>
      )}

      {((!useDemo && !rLoading && !rError && report?.recommendations?.length > 0) ||
        (useDemo && effectiveReport?.recommendations?.length > 0)) && (
        <>
          <div className="section-header">💼 今日建議（QSREC）</div>
          {(useDemo ? effectiveReport : report).recommendations.map((t, i) => (
            <TradeCard key={i} trade={t} />
          ))}
        </>
      )}

      {!useDemo &&
        !rLoading &&
        !rError &&
        (!report?.recommendations?.length || report.recommendations.length === 0) && (
        <p className="page-subtitle" style={{ opacity: 0.75, marginTop: 8 }}>
          今日尚無 QSREC 建議或報告尚未寫入。
        </p>
      )}
    </>
  );
}
