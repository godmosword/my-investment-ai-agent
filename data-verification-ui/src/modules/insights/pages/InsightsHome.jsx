import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PORTAL_PHASE4_CTA, PORTAL_PHASE4_GATE0 } from "../../../constants/portalPhase4";

/** Tab／deep-dive 延遲載入：縮小 Insights 首屏 async chunk（對齊 Master Plan §3.6）。 */
const DailyBriefPage = lazy(() => import("../../daily-brief/pages/DailyBriefPage"));
const QuantHome = lazy(() => import("../../quant-trading/pages/QuantHome"));
const EarningsInsightHome = lazy(() => import("./EarningsInsightHome"));
const PaperLifecycleHome = lazy(() => import("./PaperLifecycleHome"));
const ScenarioPlannerHome = lazy(() => import("./ScenarioPlannerHome"));
const SymbolDeepDive = lazy(() => import("./SymbolDeepDive"));
const TrackRecordHome = lazy(() => import("./TrackRecordHome"));
const OptionsFlowHome = lazy(() => import("./OptionsFlowHome"));

const tabFallback = <div className="loading text-[13px] text-white/60">載入中…</div>;

const TABS = [
  { id: "daily", label: "今日建議", testId: "insights-tab-daily" },
  { id: "earnings", label: "財報行事曆", testId: "insights-tab-earnings" },
  { id: "paper", label: "紙上生命週期", testId: "insights-tab-paper" },
  { id: "track-record", label: "Track Record", testId: "insights-tab-track-record" },
  { id: "scenario", label: "情境建議", testId: "insights-tab-scenario" },
  { id: "signals", label: "訊號", testId: "insights-tab-signals" },
  { id: "options", label: "選擇權流", testId: "insights-tab-options" },
];

const TAB_IDS = new Set(TABS.map((t) => t.id));

export default function InsightsHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [active, setActive] = useState("daily");
  const activeLabel = useMemo(() => TABS.find((t) => t.id === active)?.label ?? "今日建議", [active]);
  const symbolQs = useMemo(() => String(searchParams.get("symbol") || "").trim().toUpperCase(), [searchParams]);

  useEffect(() => {
    const fromUrl = String(searchParams.get("tab") || "").trim();
    if (fromUrl && TAB_IDS.has(fromUrl)) {
      setActive(fromUrl);
    }
  }, [searchParams]);

  const selectTab = (id) => {
    setActive(id);
    const next = new URLSearchParams(searchParams);
    if (id === "daily") next.delete("tab");
    else next.set("tab", id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div data-testid="insights-home">
      {symbolQs ? (
        <Suspense fallback={tabFallback}>
          <SymbolDeepDive />
        </Suspense>
      ) : null}
      <div
        data-testid="insights-workbench-intro"
        className="card workbench-secondary-panel mb-3 border border-emerald-500/20 bg-emerald-950/[0.08] p-3 text-[12px] leading-relaxed text-white/80"
      >
        <span data-testid="workbench-primary-question" className="font-semibold text-emerald-100/95">工作台</span>
        ：標的深挖、紙上部位、情境與訊號在此切換；題材脈動去「科技即時報／專欄」，宏觀狀態到「數據儀表板」。
        路徑目標 ≤ {PORTAL_PHASE4_GATE0.maxWorkbenchPathClicks} 次點擊。
        <span data-testid="workbench-data-health-chip" className="ml-2 rounded border border-emerald-300/20 px-2 py-0.5 text-[11px] text-emerald-100/75">
          source: API
        </span>
        <div className="mt-2 flex flex-wrap gap-2">
          <Link
            to="/news"
            data-testid="portal-cta-insights-to-news"
            className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
          >
            {PORTAL_PHASE4_CTA.workbenchToNews}
          </Link>
          <Link
            to="/columns"
            data-testid="portal-cta-insights-to-columns"
            className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
          >
            {PORTAL_PHASE4_CTA.workbenchToColumns}
          </Link>
        </div>
      </div>
      <div className="mb-3 flex flex-nowrap items-center gap-2 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Insights tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            data-testid={tab.testId}
            className={`min-h-[36px] shrink-0 rounded border px-3 py-1.5 text-[12px] font-semibold ${
              active === tab.id
                ? "border-emerald-500/40 bg-emerald-500/[0.08] text-emerald-100/90"
                : "border-white/15 text-white/70 hover:bg-white/[0.04]"
            }`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={activeLabel}>
        <Suspense fallback={tabFallback}>
          {active === "daily" ? <DailyBriefPage /> : null}
          {active === "earnings" ? <EarningsInsightHome /> : null}
          {active === "paper" ? <PaperLifecycleHome /> : null}
          {active === "track-record" ? <TrackRecordHome /> : null}
          {active === "scenario" ? <ScenarioPlannerHome /> : null}
          {active === "signals" ? <QuantHome /> : null}
          {active === "options" ? <OptionsFlowHome /> : null}
        </Suspense>
      </div>
    </div>
  );
}
