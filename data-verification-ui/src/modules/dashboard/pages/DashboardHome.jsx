import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import CatalystCalendar from "../../../components/CatalystCalendar";
import ComputeMemoryPanel from "../../../components/ComputeMemoryPanel";
import OnchainMetricsPanel from "../../../components/OnchainMetricsPanel";
import Sparkline from "../../../components/Sparkline";
import TodayBtcSnapshotStrip from "../../../components/TodayBtcSnapshotStrip";
import { useMacroSnapshot } from "../../../hooks/useApi";
import { PORTAL_PHASE4_GATE0 } from "../../../constants/portalPhase4";

const DASHBOARD_TABS = [
  { id: "overview", label: "宏觀總覽", testId: "dashboard-tab-overview" },
  { id: "depth", label: "市場深度", testId: "dashboard-tab-depth" },
];
const DASHBOARD_TAB_IDS = new Set(DASHBOARD_TABS.map((t) => t.id));

function formatValue(indicator) {
  if (!indicator) return "N/A";
  if (indicator.display) return indicator.display;
  const n = Number(indicator.value);
  if (!Number.isFinite(n)) return "N/A";
  if (indicator.unit === "USD") return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatChange(value, unit = "%") {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(unit === "bp" ? 1 : 2)}${unit}`;
}

function toneFor(indicator) {
  const n = Number(indicator?.change_5d ?? indicator?.change_1d);
  if (!Number.isFinite(n)) return "neutral";
  return n > 0 ? "up" : n < 0 ? "down" : "neutral";
}

function deltaClass(indicator) {
  const tone = toneFor(indicator);
  if (tone === "up") return "delta-up";
  if (tone === "down") return "delta-down";
  return "delta-flat";
}

function MacroCard({ indicator }) {
  const tone = toneFor(indicator);
  return (
    <article
      className="metric-card flex min-h-[168px] flex-col gap-2"
      data-testid={`macro-indicator-${indicator.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="metric-label">{indicator.label}</div>
          <div className="metric-value">{formatValue(indicator)}</div>
        </div>
        <span className={`metric-delta ${deltaClass(indicator)}`}>
          5D {formatChange(indicator.change_5d, indicator.change_unit || "%")}
        </span>
      </div>
      <div className="mt-auto">
        <Sparkline values={indicator.spark || []} tone={tone} label={`${indicator.label} sparkline`} />
      </div>
      <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--muted)]">
        <span>1D {formatChange(indicator.change_1d, indicator.change_unit || "%")}</span>
        <span className="truncate">{indicator.source}</span>
      </div>
    </article>
  );
}

function regimeTone(label) {
  if (label === "risk_on") return "regime-on";
  if (label === "risk_off") return "regime-off";
  return "regime-neutral";
}

/** 三態 driver 分數 mini-bar：-1 左紅 / 0 中性 / +1 右綠（對齊 regime 調色板）。 */
function DriverScoreBar({ score }) {
  const s = Number(score) || 0;
  return (
    <span data-testid="regime-driver-bar" className="inline-flex h-1.5 w-10 overflow-hidden rounded bg-white/10" aria-hidden="true">
      <span className="h-full w-1/2 border-r border-white/15">
        {s < 0 ? <span className="block h-full bg-rose-400/80" /> : null}
      </span>
      <span className="h-full w-1/2">
        {s > 0 ? <span className="block h-full bg-emerald-400/80" /> : null}
      </span>
    </span>
  );
}

function RegimePanel({ regime }) {
  const drivers = regime?.drivers ?? [];
  const label = regime?.label ?? "neutral";
  return (
    <section className="card h-full" data-testid="macro-regime-panel">
      <div className="card-title">Regime Breakdown</div>
      <div className={`regime-badge ${regimeTone(label)}`}>{label.replace("_", " ").toUpperCase()} · {regime?.score ?? 0}</div>
      <div className="space-y-2">
        {drivers.map((driver) => (
          <div key={driver.name} className="flex items-center justify-between gap-3 text-[13px]">
            <span className="text-[var(--muted)]">{driver.name}</span>
            <div className="flex items-center gap-2">
              <DriverScoreBar score={driver.score} />
              <span
                className={
                  driver.score > 0
                    ? "text-emerald-300/90"
                    : driver.score < 0
                      ? "text-rose-300/90"
                      : "text-[var(--muted)]"
                }
              >
                {driver.note} · {driver.score > 0 ? "+" : ""}
                {driver.score}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function DashboardHome() {
  const macro = useMacroSnapshot();
  const data = macro.data;
  const order = data?.indicator_order ?? [];
  const indicators = order.map((id) => data?.indicators?.[id]).filter(Boolean);
  const [offlineHint, setOfflineHint] = useState("");
  const [isOnline, setIsOnline] = useState(() =>
    typeof globalThis.navigator !== "undefined" ? globalThis.navigator.onLine : true,
  );

  const [searchParams, setSearchParams] = useSearchParams();
  const [active, setActive] = useState("overview");
  const activeLabel = useMemo(
    () => DASHBOARD_TABS.find((t) => t.id === active)?.label ?? "宏觀總覽",
    [active],
  );

  useEffect(() => {
    const fromUrl = String(searchParams.get("tab") || "").trim();
    if (fromUrl && DASHBOARD_TAB_IDS.has(fromUrl)) {
      setActive(fromUrl);
    }
  }, [searchParams]);

  const selectTab = (id) => {
    setActive(id);
    const next = new URLSearchParams(searchParams);
    if (id === "overview") next.delete("tab");
    else next.set("tab", id);
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    const bump = () => setIsOnline(Boolean(globalThis.navigator?.onLine));
    globalThis.addEventListener?.("online", bump);
    globalThis.addEventListener?.("offline", bump);
    return () => {
      globalThis.removeEventListener?.("online", bump);
      globalThis.removeEventListener?.("offline", bump);
    };
  }, []);

  useEffect(() => {
    try {
      setOfflineHint(String(globalThis.localStorage?.getItem("qsi_offline_macro_as_of_hint") ?? "").trim());
    } catch {
      setOfflineHint("");
    }
  }, []);

  useEffect(() => {
    const asOf = data?.as_of;
    if (!asOf || typeof asOf !== "string") return;
    try {
      globalThis.localStorage?.setItem("qsi_offline_macro_as_of_hint", asOf);
    } catch {
      /* ignore */
    }
  }, [data?.as_of]);

  const showOfflineStrip = !isOnline && Boolean(offlineHint);

  return (
    <div data-testid="dashboard-home" className="px-3 py-4 pb-24 md:px-0 md:pb-0">
      <div className="page-header">
        <div className="page-title">數據儀表板</div>
        <div className="page-subtitle">
          Macro snapshot · {data?.as_of ? new Date(data.as_of).toLocaleString("zh-TW", { hour12: false }) : "loading"}
          {data?.cached ? " · cached" : ""}
        </div>
      </div>

      <div
        data-testid="dashboard-workbench-intro"
        className="card workbench-secondary-panel mb-3 border border-cyan-500/15 bg-cyan-950/10 p-3 text-[12px] leading-relaxed text-white/80"
      >
        <span data-testid="workbench-primary-question" className="font-semibold text-cyan-100/95">工作台 · 宏觀一問</span>
        ：先看 regime 與催化剂，再回到
        <Link to="/insights" className="mx-1 text-cyan-200 underline-offset-2 hover:text-cyan-100 hover:underline">
          觀點
        </Link>
        或
        <Link to="/portfolio" className="mx-1 text-cyan-200 underline-offset-2 hover:text-cyan-100 hover:underline">
          持倉
        </Link>
        對照部位。主戰場仍以觀點／持倉為核心（路徑目標 ≤ {PORTAL_PHASE4_GATE0.maxWorkbenchPathClicks} 次點擊）。
        <span data-testid="workbench-data-health-chip" className="ml-2 rounded border border-cyan-300/20 px-2 py-0.5 text-[11px] text-cyan-100/75">
          source: {data?.source || "macro"}
        </span>
      </div>

      {showOfflineStrip ? (
        <div className="error-msg mb-3" role="status" data-testid="dashboard-offline-asof-hint">
          離線中：macro 最近一次成功載入為{" "}
          <code>{new Date(offlineHint).toLocaleString("zh-TW", { hour12: false })}</code>（僅供參考，非即時）。
        </div>
      ) : null}

      <TodayBtcSnapshotStrip />

      {macro.isLoading ? <div className="loading" data-testid="macro-dashboard-loading">載入 macro snapshot…</div> : null}
      {macro.error ? (
        <div className="error-msg mb-3" data-testid="macro-dashboard-error">
          無法載入 macro snapshot：<code>{macro.error.message}</code>
        </div>
      ) : null}

      <div
        className="mb-3 flex flex-wrap items-center gap-2 px-1"
        role="tablist"
        aria-label="Dashboard tabs"
      >
        {DASHBOARD_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            data-testid={tab.testId}
            className={`min-h-[36px] rounded border px-3 py-1.5 text-[12px] font-semibold ${
              active === tab.id
                ? "border-cyan-500/40 bg-cyan-500/[0.08] text-cyan-100/90"
                : "border-white/15 text-white/70 hover:bg-white/[0.04]"
            }`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={activeLabel}>
        {active === "overview" ? (
          <>
            {indicators.length > 0 ? (
              <div
                className="workbench-primary-panel mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
                data-testid="macro-indicator-grid"
                data-workbench-role="primary"
              >
                {indicators.map((indicator) => (
                  <MacroCard key={indicator.id} indicator={indicator} />
                ))}
              </div>
            ) : null}
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.2fr_0.8fr]">
              <CatalystCalendar catalysts={data?.catalysts ?? []} />
              <RegimePanel regime={data?.regime} />
            </div>
          </>
        ) : null}
        {active === "depth" ? (
          <>
            <ComputeMemoryPanel />
            <OnchainMetricsPanel />
          </>
        ) : null}
      </div>
    </div>
  );
}
