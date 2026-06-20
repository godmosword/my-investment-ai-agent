/**
 * 不尋常期權流表（presentational）：桌機表格 + 手機卡片。
 * 數字由後端注入，前端只格式化、不重算（無數據幻覺紅線）。
 *
 * @param {{ signals?: Array<{
 *   trade_date?: string, option_ticker?: string, signal_type?: string,
 *   score?: number|null, premium?: number|null, volume?: number|null,
 *   open_interest?: number|null, rationale?: string
 * }> }} props
 */

const SIGNAL_LABELS = {
  volume_oi: "量/OI 異常",
  sweep: "掃單",
  block: "大宗",
  premium: "大額",
  concentration: "集中",
};

function signalLabel(type) {
  return SIGNAL_LABELS[String(type || "")] || String(type || "—");
}

function signalChipClass(type) {
  if (type === "sweep" || type === "block") return "border-amber-400/40 bg-amber-500/[0.1] text-amber-100/90";
  if (type === "volume_oi") return "border-sky-400/40 bg-sky-500/[0.1] text-sky-100/90";
  return "border-white/15 text-white/70";
}

function num(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-US");
}

function money(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

/** OCC ticker O:MU260116C00100000 → { type, strike, expiry }；解析失敗回 null。 */
function parseOcc(ticker) {
  const raw = String(ticker || "");
  const body = raw.startsWith("O:") ? raw.slice(2) : raw;
  if (body.length < 15) return null;
  const tail = body.slice(-15);
  const yy = tail.slice(0, 2);
  const mm = tail.slice(2, 4);
  const dd = tail.slice(4, 6);
  const cp = tail.slice(6, 7).toUpperCase();
  const strikeRaw = Number(tail.slice(7));
  if (!Number.isFinite(strikeRaw) || (cp !== "C" && cp !== "P")) return null;
  return {
    type: cp === "C" ? "Call" : "Put",
    strike: strikeRaw / 1000,
    expiry: `20${yy}-${mm}-${dd}`,
  };
}

function ContractLabel({ ticker }) {
  const occ = parseOcc(ticker);
  if (!occ) return <span className="font-mono text-[12px] text-white/85">{ticker || "—"}</span>;
  const tone = occ.type === "Call" ? "text-emerald-200/90" : "text-rose-200/90";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`text-[12px] font-semibold ${tone}`}>{occ.type} ${occ.strike}</span>
      <span className="text-[11px] text-white/50">{occ.expiry}</span>
    </span>
  );
}

function ScoreBar({ score }) {
  const pct = Math.max(0, Math.min(1, Number(score) || 0)) * 100;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-1.5 w-12 overflow-hidden rounded bg-white/10">
        <span className="block h-full bg-amber-300/80" style={{ width: `${pct}%` }} />
      </span>
      <span className="text-[11px] text-white/60">{(Number(score) || 0).toFixed(2)}</span>
    </span>
  );
}

export default function UnusualFlowTable({ signals = [] }) {
  if (!signals || signals.length === 0) {
    return (
      <div data-testid="options-flow-empty" className="card p-3 text-[13px] text-white/60">
        近期無不尋常期權流訊號。
      </div>
    );
  }

  return (
    <div data-testid="options-flow-table" className="card p-3">
      <div className="mb-2 text-[12px] font-semibold text-white/80">近期不尋常期權流（{signals.length}）</div>

      {/* 桌機：表格 */}
      <div className="hidden overflow-x-auto rounded border border-[color:var(--border)] md:block">
        <table className="w-full min-w-[680px] text-left text-[12px]">
          <thead className="bg-[var(--panel)] text-[11px] uppercase text-[var(--muted)]">
            <tr>
              <th className="px-3 py-2">類型</th>
              <th className="px-3 py-2">合約</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">Premium</th>
              <th className="px-3 py-2">Volume</th>
              <th className="px-3 py-2">OI</th>
              <th className="px-3 py-2">說明</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => (
              <tr key={`${s.option_ticker}-${i}`} data-testid="options-flow-row" className="border-t border-[color:var(--border)]">
                <td className="px-3 py-2">
                  <span className={`rounded border px-2 py-0.5 text-[11px] ${signalChipClass(s.signal_type)}`}>{signalLabel(s.signal_type)}</span>
                </td>
                <td className="px-3 py-2"><ContractLabel ticker={s.option_ticker} /></td>
                <td className="px-3 py-2"><ScoreBar score={s.score} /></td>
                <td className="px-3 py-2 font-mono text-white/85">{money(s.premium)}</td>
                <td className="px-3 py-2 font-mono text-white/85">{num(s.volume)}</td>
                <td className="px-3 py-2 font-mono text-white/85">{num(s.open_interest)}</td>
                <td className="px-3 py-2 text-white/60">{s.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 手機：卡片 */}
      <ul className="flex flex-col gap-2 md:hidden">
        {signals.map((s, i) => (
          <li key={`${s.option_ticker}-${i}-m`} data-testid="options-flow-card" className="rounded border border-[color:var(--border)] p-2.5">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className={`rounded border px-2 py-0.5 text-[11px] ${signalChipClass(s.signal_type)}`}>{signalLabel(s.signal_type)}</span>
              <ScoreBar score={s.score} />
            </div>
            <div className="mb-1"><ContractLabel ticker={s.option_ticker} /></div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-white/70">
              <span>Premium {money(s.premium)}</span>
              <span>Vol {num(s.volume)}</span>
              <span>OI {num(s.open_interest)}</span>
            </div>
            {s.rationale ? <div className="mt-1 text-[11px] text-white/55">{s.rationale}</div> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
