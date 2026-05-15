import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PORTAL_PHASE4_GATE0 } from "../../../constants/portalPhase4";
import DailyBriefPage from "../../daily-brief/pages/DailyBriefPage";
import QuantHome from "../../quant-trading/pages/QuantHome";
import PaperLifecycleHome from "./PaperLifecycleHome";
import ScenarioPlannerHome from "./ScenarioPlannerHome";
import SymbolDeepDive from "./SymbolDeepDive";
import TrackRecordHome from "./TrackRecordHome";

const TABS = [
  { id: "daily", label: "今日建議", testId: "insights-tab-daily" },
  { id: "paper", label: "紙上生命週期", testId: "insights-tab-paper" },
  { id: "track-record", label: "Track Record", testId: "insights-tab-track-record" },
  { id: "scenario", label: "情境建議", testId: "insights-tab-scenario" },
  { id: "signals", label: "訊號", testId: "insights-tab-signals" },
];

const TAB_IDS = new Set(TABS.map((t) => t.id));

export default function InsightsHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [active, setActive] = useState("daily");
  const activeLabel = useMemo(() => TABS.find((t) => t.id === active)?.label ?? "今日建議", [active]);

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
      <SymbolDeepDive />
      <div
        data-testid="insights-workbench-intro"
        className="card mb-3 border border-emerald-500/20 bg-emerald-950/15 p-3 text-[12px] leading-relaxed text-white/80"
      >
        <span className="font-semibold text-emerald-100/95">工作台</span>
        ：標的深挖、紙上部位、情境與訊號在此分頁切換。讀題材與即時脈動請用「科技即時報／專欄」。主戰場以
        <span className="text-emerald-100/90"> 觀點、持倉 </span>
        為核心；宏觀狀態請到「數據儀表板」。關鍵路徑目標 ≤ {PORTAL_PHASE4_GATE0.maxWorkbenchPathClicks}{" "}
        次點擊（人測錨點）。
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2 px-1" role="tablist" aria-label="Insights tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            data-testid={tab.testId}
            className={`rounded border px-3 py-1.5 text-[12px] font-semibold ${
              active === tab.id
                ? "border-emerald-500/60 bg-emerald-500/20 text-emerald-100"
                : "border-white/15 text-white/70 hover:bg-white/5"
            }`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={activeLabel}>
        {active === "daily" ? <DailyBriefPage /> : null}
        {active === "paper" ? <PaperLifecycleHome /> : null}
        {active === "track-record" ? <TrackRecordHome /> : null}
        {active === "scenario" ? <ScenarioPlannerHome /> : null}
        {active === "signals" ? <QuantHome /> : null}
      </div>
    </div>
  );
}
