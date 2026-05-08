import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import SymbolFocusBar from "../components/SymbolFocusBar";
import TodayBtcSnapshotStrip from "../components/TodayBtcSnapshotStrip";
import AsOfChip from "../components/common/AsOfChip";
import BriefProfileBar from "../components/report/BriefProfileBar";
import { normalizeReportProfile } from "../components/report/reportProfiles";

const STRUCTURED_FLAG = import.meta.env.VITE_STRUCTURED_REPORT === "1";

const PIPELINE_STEPS = [
  { key: "research",  label: "研究" },
  { key: "validate",  label: "驗證" },
  { key: "signal",    label: "信號" },
  { key: "review",    label: "審核" },
  { key: "dispatch",  label: "發送" },
];

function SignalPipeline({ warRoom }) {
  const gateStatus = warRoom?.gate_status ?? warRoom?.gate ?? null;
  const passedStep = gateStatus === "PASS" ? 5 : gateStatus != null ? 2 : 1;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        marginBottom: 12,
        padding: "10px 14px",
        background: "rgba(12, 18, 34, 0.6)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        overflow: "hidden",
      }}
      role="status"
      aria-label="信號 pipeline 狀態"
    >
      {PIPELINE_STEPS.map((step, i) => {
        const done = i < passedStep;
        const active = i === passedStep - 1;
        return (
          <div key={step.key} style={{ display: "flex", alignItems: "center", flex: i < 4 ? "1 1 0" : undefined }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 44 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  border: `2px solid ${done ? "var(--accent)" : active ? "var(--yellow)" : "var(--border)"}`,
                  background: done
                    ? "var(--accent-soft)"
                    : active
                      ? "rgba(251,191,36,0.1)"
                      : "rgba(255,255,255,0.02)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  fontWeight: 700,
                  color: done ? "var(--accent)" : active ? "var(--yellow)" : "var(--muted)",
                  transition: "all 0.3s",
                }}
              >
                {done ? "✓" : i + 1}
              </div>
              <span style={{ fontSize: 9, color: done ? "var(--accent)" : "var(--muted)", fontWeight: done ? 600 : 400 }}>
                {step.label}
              </span>
            </div>
            {i < 4 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: done ? "var(--accent)" : "var(--border)",
                  transition: "background 0.3s",
                  marginBottom: 14,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function Today() {
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [warRoomIntentFilter, setWarRoomIntentFilter] = useState("all");
  const [searchParams, setSearchParams] = useSearchParams();
  const rawProfile = searchParams.get("profile");
  const profile = normalizeReportProfile(rawProfile);

  useEffect(() => {
    const cur = searchParams.get("profile");
    const n = normalizeReportProfile(cur);
    if (cur != null && cur !== "" && n !== cur) {
      const next = new URLSearchParams(searchParams);
      next.set("profile", n);
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const today = new Date().toISOString().slice(0, 10);
  const {
    data: metrics,
    isLoading: mLoading,
    error: mError,
    refetch: mRefetch,
    isFetching: mFetching,
  } = useMetricsLatest();
  const {
    data: report,
    isLoading: rLoading,
    error: rError,
    refetch: rRefetch,
    isFetching: rFetching,
  } = useReport(today);
  const {
    data: openPos,
    isLoading: oLoading,
    error: oError,
    refetch: oRefetch,
    isFetching: oFetching,
  } = useOpenPositions(90);
  const {
    data: warRoom,
    isLoading: wLoading,
    error: wError,
    refetch: wRefetch,
    isFetching: wFetching,
  } = useWarRoomLatest();

  const forceDemo = useGlassboxDemoMode();
  const allSettled = !mLoading && !rLoading && !oLoading;
  const apiAllFailed = allSettled && Boolean(mError && rError && oError);
  const useDemo = forceDemo || apiAllFailed;

  const effectiveMetrics = useDemo ? MOCK_METRICS_LATEST : metrics ?? null;
  const effectiveOpen = useDemo ? MOCK_OPEN_POSITIONS : openPos ?? null;
  const effectiveReport = useDemo ? mockReportForDate(today) : report ?? null;

  const openCount = Array.isArray(effectiveOpen) ? effectiveOpen.length : 0;
  const longCount =
    effectiveOpen?.filter((t) => t.direction?.toUpperCase() === "LONG").length ?? 0;
  const shortCount =
    effectiveOpen?.filter((t) => t.direction?.toUpperCase() === "SHORT").length ?? 0;

  const regime = regimeInfo(effectiveMetrics?.avg_risk_score);

  const showMetricsBlock =
    useDemo || (!mLoading && !mError && metrics);
  const metricsLoadingUi = !useDemo && mLoading && !mError;

  return (
    <>
      <PositionHealthStrip
        openCount={openCount}
        loading={useDemo ? false : oLoading}
        error={useDemo ? null : oError}
        onRetryOpen={useDemo ? undefined : () => oRefetch()}
        retryingOpen={useDemo ? false : oFetching}
      />

      {!online && (
        <div
          data-testid="today-offline-banner"
          className="glassbox-demo-banner glassbox-demo-banner--today"
          role="status"
          style={{ borderColor: "var(--border)", marginBottom: 8 }}
        >
          目前離線；API 仍採 NetworkOnly（見 <code>PWA_OFFLINE.md</code>）。恢復網路後請手動刷新以取得最新戰情室資料。
        </div>
      )}

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

      {/* Regime ambient glow overlay */}
      {showMetricsBlock && effectiveMetrics && (
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            height: "40vh",
            pointerEvents: "none",
            zIndex: 0,
            background:
              regime.cls === "regime-on"
                ? "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(5,150,105,0.06), transparent 70%)"
                : regime.cls === "regime-off"
                  ? "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(220,38,38,0.06), transparent 70%)"
                  : "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(217,119,6,0.05), transparent 70%)",
            transition: "background 1.2s ease",
          }}
        />
      )}

      <div className="page-header" style={{ position: "relative", zIndex: 1 }}>
        <div className="page-title">今日戰情室</div>
        <div
          className="page-subtitle"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "8px 12px",
            marginTop: 6,
          }}
        >
          <BriefProfileBar
            value={profile}
            onChange={(next) => {
              const n = normalizeReportProfile(next);
              const nextParams = new URLSearchParams(searchParams);
              nextParams.set("profile", n);
              setSearchParams(nextParams, { replace: true });
            }}
          />
          {STRUCTURED_FLAG ? (
            <Link
              to={`/report/${today}?profile=${encodeURIComponent(profile)}`}
              style={{ fontSize: 13, color: "var(--accent)", textDecoration: "none" }}
            >
              開啟今日區塊視圖 →
            </Link>
          ) : null}
        </div>
        {showMetricsBlock && effectiveMetrics ? (
          <div style={{ marginTop: 8 }}>
            <AsOfChip
              asOf={effectiveMetrics.timestamp}
              source={useDemo ? "mock · Glassbox" : "BigQuery · daily_metrics"}
              label="指標更新"
              polling={!useDemo && Boolean(mFetching)}
            />
          </div>
        ) : null}
      </div>

      <SymbolFocusBar compact />

      {!useDemo && <TodayBtcSnapshotStrip />}

      <div className="section-header subtle" style={{ position: "relative", zIndex: 1 }}>
        War Room（Gate / Scratchpad / Intent）
      </div>

      {/* Signal pipeline progress indicator */}
      <SignalPipeline warRoom={warRoom} />

      <WarRoomCard
        warRoom={warRoom}
        loading={useDemo ? false : wLoading}
        retrying={useDemo ? false : wFetching}
        error={useDemo ? null : wError}
        intentStatusFilter={warRoomIntentFilter}
        onIntentStatusChange={setWarRoomIntentFilter}
        onWarRoomRetry={useDemo ? undefined : () => wRefetch()}
      />

      {!useDemo && mError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          {effectiveMetrics ? "最新指標暫時未更新，保留上一筆成功資料顯示。" : "無法載入最新指標（首次載入失敗）。"}
          <div style={{ marginTop: 6 }}>
            <code>/api/metrics/latest</code>：{mError.message}
          </div>
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.9 }}>
            請確認 FastAPI 已啟動、BigQuery 憑證就緒，並檢查 <code>VITE_API_URL</code>。
            若僅預覽 UI，可設 <code>VITE_GLASSBOX_MOCK=1</code>。
          </div>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="war-room-retry"
              disabled={mFetching}
              onClick={() => mRefetch()}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel)",
                color: "var(--text)",
                cursor: mFetching ? "not-allowed" : "pointer",
              }}
            >
              {mFetching ? "重試中…" : "重試指標"}
            </button>
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
      {(useDemo || (!oLoading && effectiveOpen)) && Array.isArray(effectiveOpen) && (
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
      {!useDemo && oError ? (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          {effectiveOpen ? "OPEN 部位暫時未更新，保留上一筆成功資料顯示。" : "無法載入 OPEN 部位。"}
          <div style={{ marginTop: 6 }}>
            <code>/api/positions/open</code>：{oError.message}
          </div>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="war-room-retry"
              disabled={oFetching}
              onClick={() => oRefetch()}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel)",
                color: "var(--text)",
                cursor: oFetching ? "not-allowed" : "pointer",
              }}
            >
              {oFetching ? "重試中…" : "重試持倉"}
            </button>
          </div>
        </div>
      ) : null}

      {!useDemo && rError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          {effectiveReport ? "今日報告暫時未更新，保留上一筆成功資料顯示。" : "無法載入今日報告。"}
          <div style={{ marginTop: 6 }}>{rError.message}</div>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="war-room-retry"
              disabled={rFetching}
              onClick={() => rRefetch()}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel)",
                color: "var(--text)",
                cursor: rFetching ? "not-allowed" : "pointer",
              }}
            >
              {rFetching ? "重試中…" : "重試報告"}
            </button>
          </div>
        </div>
      )}

      {((!useDemo && !rLoading && effectiveReport?.recommendations?.length > 0) ||
        (useDemo && effectiveReport?.recommendations?.length > 0)) && (
        <>
          <div className="section-header">💼 今日建議（QSREC）</div>
          {(useDemo ? effectiveReport : effectiveReport).recommendations.map((t, i) => (
            <TradeCard key={i} trade={t} />
          ))}
        </>
      )}

      {!useDemo &&
        !rLoading &&
        !effectiveReport?.recommendations?.length && (
        <p className="page-subtitle" style={{ opacity: 0.75, marginTop: 8 }}>
          今日尚無 QSREC 建議或報告尚未寫入。
        </p>
      )}
    </>
  );
}
