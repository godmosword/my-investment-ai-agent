import { useMemo, useState } from "react";
import DailyBriefPage from "../../daily-brief/pages/DailyBriefPage";
import QuantHome from "../../quant-trading/pages/QuantHome";
import PaperLifecycleHome from "./PaperLifecycleHome";
import SymbolDeepDive from "./SymbolDeepDive";
import TrackRecordHome from "./TrackRecordHome";

const TABS = [
  { id: "daily", label: "今日建議", testId: "insights-tab-daily" },
  { id: "paper", label: "紙上生命週期", testId: "insights-tab-paper" },
  { id: "track-record", label: "Track Record", testId: "insights-tab-track-record" },
  { id: "signals", label: "訊號", testId: "insights-tab-signals" },
];

export default function InsightsHome() {
  const [active, setActive] = useState("daily");
  const activeLabel = useMemo(() => TABS.find((t) => t.id === active)?.label ?? "今日建議", [active]);

  return (
    <div data-testid="insights-home">
      <SymbolDeepDive />
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
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={activeLabel}>
        {active === "daily" ? <DailyBriefPage /> : null}
        {active === "paper" ? <PaperLifecycleHome /> : null}
        {active === "track-record" ? <TrackRecordHome /> : null}
        {active === "signals" ? <QuantHome /> : null}
      </div>
    </div>
  );
}
