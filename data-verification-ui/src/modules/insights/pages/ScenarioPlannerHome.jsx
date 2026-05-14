import { useScenarioSuggestions } from "../../../hooks/useApi";

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

  return (
    <div data-testid="scenario-planner-home" className="space-y-3 text-[13px] text-white/85">
      <p className="rounded border border-amber-500/30 bg-amber-950/20 px-2 py-1.5 text-[12px] text-amber-100">{data.disclaimer}</p>
      <div className="grid gap-2 md:grid-cols-3">
        {(data.scenarios || []).map((s) => (
          <div key={s.id} className="rounded border border-white/10 bg-black/30 p-2" data-testid={`scenario-card-${s.id}`}>
            <div className="text-[11px] uppercase text-cyan-200">{s.label}</div>
            <div className="mt-1 font-mono text-[12px] text-white/90">shift {s.notional_shift_pct}%</div>
            <div className="mt-1 text-[11px] text-white/60">{s.notes}</div>
          </div>
        ))}
      </div>
      <div className="rounded border border-white/10 bg-white/[0.03] p-2">
        <div className="text-[11px] font-semibold uppercase text-cyan-200">Portfolio</div>
        <div className="mt-1 font-mono text-[12px]">HHI {data.portfolio?.concentration_hhi}</div>
        <div className="mt-1 text-[11px] text-white/60">
          {(data.portfolio?.top_symbols || []).map((t) => `${t.symbol} ${t.weight_pct}%`).join(" · ") || "—"}
        </div>
      </div>
      {data.target_hints?.length ? (
        <div className="rounded border border-white/10 bg-white/[0.03] p-2" data-testid="scenario-target-hints">
          <div className="text-[11px] font-semibold uppercase text-cyan-200">Target hints（僅 intent 欄位）</div>
          <ul className="mt-1 list-inside list-disc space-y-1 text-[12px] text-white/75">
            {data.target_hints.slice(0, 8).map((h) => (
              <li key={h.signal_id}>
                <span className="font-mono text-white/90">{h.asset}</span>
                {h.in_portfolio ? " · book" : ""}
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
