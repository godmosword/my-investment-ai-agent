import { useScenarioSuggestions } from "../../../hooks/useApi";
import { finiteNumber } from "../../../utils/finiteNumber";

const SCENARIO_TITLE_BY_ID = {
  defensive: "防守偏向",
  base: "維持結構",
  opportunistic: "伺機減碼",
};

function scenarioCardTitle(id) {
  return SCENARIO_TITLE_BY_ID[id] ?? "UNKNOWN";
}

function scenarioCardNotes(notes) {
  return typeof notes === "string" && notes.trim() !== "" ? notes : "UNKNOWN";
}

export default function ScenarioPlannerHome() {
  const q = useScenarioSuggestions();

  if (q.isLoading) {
    return (
      <div data-testid="scenario-planner-loading" className="text-[13px] text-white/60">
        載入情境建議…
      </div>
    );
  }
  if (q.isError) {
    return (
      <div data-testid="scenario-planner-error" className="rounded border border-red-500/40 bg-red-950/30 p-3 text-[13px] text-red-200">
        無法載入：{q.error instanceof Error ? q.error.message : String(q.error)}
      </div>
    );
  }
  const data = q.data;
  if (data?.disabled) {
    return (
      <div data-testid="scenario-planner-disabled" className="rounded border border-white/15 bg-white/[0.03] p-3 text-[13px] text-white/70">
        此環境未啟用情境引擎（後端需 <code className="text-cyan-200">SCENARIO_OPTIMIZER_ENABLED=1</code>）。僅供內部規劃，不下單。
      </div>
    );
  }

  const hhi = finiteNumber(data.portfolio?.concentration_hhi);
  const topSymbols = Array.isArray(data.portfolio?.top_symbols) ? data.portfolio.top_symbols : [];
  const topLine = topSymbols.length
    ? topSymbols.map((t) => `${t.symbol} ${t.weight_pct}%`).join(" · ")
    : "UNKNOWN";
  const scenarios = Array.isArray(data.scenarios) ? data.scenarios : [];

  return (
    <div data-testid="scenario-planner-home" className="space-y-3 text-[13px] text-white/85">
      <p className="rounded border border-amber-500/30 bg-amber-950/20 px-2 py-1.5 text-[12px] text-amber-100">{data.disclaimer}</p>
      {scenarios.length === 0 ? (
        <div
          data-testid="scenario-planner-empty"
          className="rounded border border-white/10 bg-white/[0.03] p-3 text-[13px] text-white/70"
          role="status"
        >
          尚無情境建議
        </div>
      ) : (
        <div className="grid gap-2 md:grid-cols-3" data-testid="scenario-card-grid">
          {scenarios.map((s) => {
            const shiftPct = finiteNumber(s.notional_shift_pct);
            return (
              <div key={s.id} className="rounded border border-white/10 bg-black/30 p-2" data-testid={`scenario-card-${s.id}`}>
                <div className="text-[11px] uppercase text-cyan-200" data-testid="scenario-title">
                  {scenarioCardTitle(s.id)}
                </div>
                <div className="mt-1 font-mono text-[12px] text-white/90" data-testid="scenario-notional-shift">
                  {shiftPct == null ? "UNKNOWN" : `名義移轉 ${shiftPct}%`}
                </div>
                <div className="mt-1 text-[11px] text-white/60" data-testid="scenario-notes">
                  {scenarioCardNotes(s.notes)}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <div className="rounded border border-white/10 bg-white/[0.03] p-2" data-testid="scenario-portfolio">
        <div className="text-[11px] font-semibold uppercase text-cyan-200" data-testid="scenario-portfolio-title">持倉</div>
        <div className="mt-1 font-mono text-[12px]">
          HHI <span data-testid="scenario-hhi">{hhi == null ? "UNKNOWN" : hhi}</span>
        </div>
        <div className="mt-1 text-[11px] text-white/60" data-testid="scenario-top-symbols">
          {topLine}
        </div>
      </div>
      {data.target_hints?.length ? (
        <div className="rounded border border-white/10 bg-white/[0.03] p-2" data-testid="scenario-target-hints">
          <div className="text-[11px] font-semibold uppercase text-cyan-200" data-testid="scenario-target-hints-title">目標提示（僅 intent）</div>
          <ul className="mt-1 list-inside list-disc space-y-1 text-[12px] text-white/75">
            {data.target_hints.slice(0, 8).map((h) => (
              <li key={h.signal_id} data-testid="scenario-target-hint">
                <span className="font-mono text-white/90">{h.asset}</span>
                {h.in_portfolio ? <span data-testid="scenario-hint-in-portfolio"> · 持倉內</span> : ""}
                {": "}
                {(h.suggestions || []).map((s) => s.text).join(" · ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
