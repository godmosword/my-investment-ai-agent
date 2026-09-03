import { useEffect, useMemo, useState } from "react";
import {
  useAnalysisBundle,
  useCreateExecutionIntent,
} from "../hooks/useApi";

const STORAGE_KEY = "qsi_risk_budget_v1";
const DEFAULT_RISK_PCT = 1.0;

function loadBudget() {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return { account_equity: "", risk_pct: DEFAULT_RISK_PCT };
    const parsed = JSON.parse(raw);
    return {
      account_equity: typeof parsed.account_equity === "number" ? String(parsed.account_equity) : "",
      risk_pct:
        typeof parsed.risk_pct === "number" && parsed.risk_pct > 0
          ? parsed.risk_pct
          : DEFAULT_RISK_PCT,
    };
  } catch {
    return { account_equity: "", risk_pct: DEFAULT_RISK_PCT };
  }
}

function persistEquity(account_equity) {
  if (account_equity === "" || account_equity == null) return "";
  const n = Number(account_equity);
  return Number.isFinite(n) ? n : "";
}

function saveBudget(account_equity, risk_pct) {
  try {
    globalThis.localStorage?.setItem(
      STORAGE_KEY,
      JSON.stringify({
        account_equity: persistEquity(account_equity),
        risk_pct: Number(risk_pct) || DEFAULT_RISK_PCT,
      }),
    );
  } catch {
    // Best-effort persistence; safe to ignore quota / privacy-mode errors.
  }
}

function toNumber(value) {
  if (value === "" || value == null) return NaN;
  const n = Number(value);
  return Number.isFinite(n) ? n : NaN;
}

function moneyFmt(n) {
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function budgetDisplay(equity, riskBudget) {
  if (equity === "" || equity == null) return "UNKNOWN";
  return moneyFmt(riskBudget);
}

function priceFmt(n) {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

/**
 * 14-day ATR from a yfinance-shaped OHLC array.
 * Each row: { time, open, high, low, close }. Returns NaN if not enough bars.
 */
function computeAtr14(priceSeries) {
  if (!Array.isArray(priceSeries) || priceSeries.length < 15) return NaN;
  const series = priceSeries.slice(-15);
  const trs = [];
  for (let i = 1; i < series.length; i += 1) {
    const bar = series[i];
    const prev = series[i - 1];
    const high = Number(bar.high);
    const low = Number(bar.low);
    const prevClose = Number(prev.close);
    if (![high, low, prevClose].every(Number.isFinite)) return NaN;
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    trs.push(tr);
  }
  if (trs.length === 0) return NaN;
  const sum = trs.reduce((acc, v) => acc + v, 0);
  return sum / trs.length;
}

function deriveMetrics({ direction, entry, stop, target, equity, riskPct }) {
  const e = toNumber(entry);
  const s = toNumber(stop);
  const t = toNumber(target);
  const eq = toNumber(equity);
  const rp = toNumber(riskPct);

  const issues = [];
  if (!Number.isFinite(e) || e <= 0) issues.push("entry 必填且 > 0");
  if (!Number.isFinite(s) || s <= 0) issues.push("stop 必填且 > 0");
  if (Number.isFinite(e) && Number.isFinite(s) && e === s) issues.push("entry 與 stop 不可相同");
  if (Number.isFinite(t) && t > 0 && Number.isFinite(e)) {
    if (direction === "LONG" && t <= e) issues.push("LONG: target 需 > entry");
    if (direction === "SHORT" && t >= e) issues.push("SHORT: target 需 < entry");
  }
  if (Number.isFinite(e) && Number.isFinite(s)) {
    if (direction === "LONG" && s >= e) issues.push("LONG: stop 需 < entry");
    if (direction === "SHORT" && s <= e) issues.push("SHORT: stop 需 > entry");
  }

  const riskPerShare = Number.isFinite(e) && Number.isFinite(s) ? Math.abs(e - s) : NaN;
  const rewardPerShare =
    Number.isFinite(e) && Number.isFinite(t) && t > 0 ? Math.abs(t - e) : NaN;
  const rr = Number.isFinite(rewardPerShare) && riskPerShare > 0 ? rewardPerShare / riskPerShare : NaN;
  const pctToStop = Number.isFinite(e) && Number.isFinite(s) && e > 0 ? Math.abs(s - e) / e : NaN;
  const pctToTarget =
    Number.isFinite(e) && Number.isFinite(t) && t > 0 && e > 0 ? Math.abs(t - e) / e : NaN;

  const riskBudget =
    Number.isFinite(eq) && eq > 0 && Number.isFinite(rp) && rp > 0 ? (eq * rp) / 100 : NaN;
  const positionShares =
    Number.isFinite(riskBudget) && riskPerShare > 0 ? Math.floor(riskBudget / riskPerShare) : NaN;
  const notional =
    Number.isFinite(positionShares) && Number.isFinite(e) ? positionShares * e : NaN;
  const actualRiskDollars =
    Number.isFinite(positionShares) && Number.isFinite(riskPerShare)
      ? positionShares * riskPerShare
      : NaN;

  return {
    issues,
    riskPerShare,
    rewardPerShare,
    rr,
    pctToStop,
    pctToTarget,
    riskBudget,
    positionShares,
    notional,
    actualRiskDollars,
    canSubmit: issues.length === 0 && Number.isFinite(positionShares) && positionShares > 0,
  };
}

function MetricRow({ label, value, sub, testId }) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-1">
      <span className="text-[12px] text-white/65">{label}</span>
      <span className="text-right">
        <span className="font-mono text-[14px] font-semibold text-white" data-testid={testId}>
          {value}
        </span>
        {sub ? <span className="ml-2 text-[11px] text-[var(--muted)]">{sub}</span> : null}
      </span>
    </div>
  );
}

export default function PortfolioRiskPanel() {
  const initial = loadBudget();
  const [equity, setEquity] = useState(initial.account_equity);
  const [riskPct, setRiskPct] = useState(String(initial.risk_pct));
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState("LONG");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [target, setTarget] = useState("");
  const [submitNote, setSubmitNote] = useState("");

  useEffect(() => {
    saveBudget(equity, riskPct);
  }, [equity, riskPct]);

  const normalizedSymbol = symbol.trim().toUpperCase();
  const bundle = useAnalysisBundle(normalizedSymbol, 30, 1);
  const atr14 = useMemo(() => computeAtr14(bundle.data?.snapshot?.price_series), [bundle.data]);
  const lastClose = useMemo(() => {
    const series = bundle.data?.snapshot?.price_series;
    if (!Array.isArray(series) || series.length === 0) return NaN;
    const n = Number(series[series.length - 1]?.close);
    return Number.isFinite(n) ? n : NaN;
  }, [bundle.data]);

  const metrics = useMemo(
    () => deriveMetrics({ direction, entry, stop, target, equity, riskPct }),
    [direction, entry, stop, target, equity, riskPct],
  );

  const applyAtrStop = () => {
    if (!Number.isFinite(atr14) || !Number.isFinite(toNumber(entry))) return;
    const e = toNumber(entry);
    const suggested = direction === "LONG" ? e - atr14 : e + atr14;
    if (suggested > 0) setStop(suggested.toFixed(2));
  };

  const applyLastClose = () => {
    if (Number.isFinite(lastClose)) setEntry(lastClose.toFixed(2));
  };

  const createIntent = useCreateExecutionIntent();

  const handleSubmit = async () => {
    if (!normalizedSymbol) {
      setSubmitNote("請填 symbol 才能送 PENDING_REVIEW（純紙上紀錄，不下單）。");
      return;
    }
    if (!metrics.canSubmit) {
      setSubmitNote("輸入未完成或不合理，無法送出。");
      return;
    }
    const e = toNumber(entry);
    const s = toNumber(stop);
    const t = toNumber(target);
    const rrLabel = Number.isFinite(metrics.rr) ? `R/R ${metrics.rr.toFixed(2)}` : "R/R —";
    const riskLabel = `${Number(riskPct).toFixed(2)}% of equity`;
    const body = {
      asset: normalizedSymbol,
      direction,
      category: "AI",
      star_rating: 1,
      thesis_one_liner: `TP/SL calc · ${rrLabel} · ${riskLabel} · ${metrics.positionShares} sh`.slice(0, 500),
      reference_entry_price: e,
      reference_stop_price: s,
      reference_target_price: Number.isFinite(t) && t > 0 ? t : null,
    };
    try {
      const row = await createIntent.mutateAsync(body);
      setSubmitNote(
        `已送入紙上 PENDING_REVIEW：${row?.signal_id || "(no id)"}（不下單；可至「紙上生命週期」追蹤）。`,
      );
    } catch (err) {
      setSubmitNote(`送出失敗：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <section
      data-testid="portfolio-risk-panel"
      className="card mb-3 border border-white/10 p-3"
      aria-label="TP/SL 計算機"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase text-cyan-200">Risk · TP/SL 計算機</div>
          <div className="text-[11px] text-[var(--muted)]">
            風險預算 = 帳戶總值 × 每筆風險 %（持久化於 localStorage `{STORAGE_KEY}`）。送出僅建立紙上 PENDING_REVIEW，**不**下單。
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <div className="card-title">風險預算</div>
          <label className="mt-2 block text-[12px] text-white/65">
            帳戶總值（USD）
            <input
              data-testid="risk-equity-input"
              type="number"
              inputMode="decimal"
              min="0"
              step="100"
              className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[14px] text-white focus:border-cyan-300/40 focus:outline-none"
              value={equity}
              onChange={(e) => setEquity(e.target.value)}
              placeholder="例：50000"
            />
          </label>
          <label className="mt-2 block text-[12px] text-white/65">
            每筆風險 %（建議 0.5–2.0）
            <input
              data-testid="risk-pct-input"
              type="number"
              inputMode="decimal"
              min="0.01"
              max="10"
              step="0.1"
              className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[14px] text-white focus:border-cyan-300/40 focus:outline-none"
              value={riskPct}
              onChange={(e) => setRiskPct(e.target.value)}
            />
          </label>
          <div className="mt-2 text-[11px] text-[var(--muted)]">
            預算 ={" "}
            <span data-testid="risk-budget-value">{budgetDisplay(equity, metrics.riskBudget)}</span>
          </div>
        </div>

        <div>
          <div className="card-title">交易參數</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="block text-[12px] text-white/65">
              標的 (symbol)
              <input
                data-testid="risk-symbol-input"
                type="text"
                className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[13px] uppercase text-white focus:border-cyan-300/40 focus:outline-none"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="NVDA"
              />
            </label>
            <div>
              <span className="text-[12px] text-white/65">方向</span>
              <div className="mt-1 flex gap-1">
                {["LONG", "SHORT"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    data-testid={`risk-direction-${d.toLowerCase()}`}
                    className={`flex-1 rounded border px-2 py-1.5 text-[12px] font-semibold ${
                      direction === d
                        ? "border-emerald-500/40 bg-emerald-500/[0.08] text-emerald-100/90"
                        : "border-white/15 text-white/70 hover:bg-white/[0.04]"
                    }`}
                    onClick={() => setDirection(d)}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2">
            <label className="block text-[12px] text-white/65">
              Entry
              <input
                data-testid="risk-entry-input"
                type="number"
                inputMode="decimal"
                step="0.01"
                className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[13px] text-white focus:border-cyan-300/40 focus:outline-none"
                value={entry}
                onChange={(e) => setEntry(e.target.value)}
              />
            </label>
            <label className="block text-[12px] text-white/65">
              Stop
              <input
                data-testid="risk-stop-input"
                type="number"
                inputMode="decimal"
                step="0.01"
                className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[13px] text-white focus:border-cyan-300/40 focus:outline-none"
                value={stop}
                onChange={(e) => setStop(e.target.value)}
              />
            </label>
            <label className="block text-[12px] text-white/65">
              Target
              <input
                data-testid="risk-target-input"
                type="number"
                inputMode="decimal"
                step="0.01"
                className="mt-1 w-full rounded border border-white/15 bg-white/[0.03] px-2 py-1.5 font-mono text-[13px] text-white focus:border-cyan-300/40 focus:outline-none"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
            <button
              type="button"
              data-testid="risk-apply-last-close"
              className="rounded border border-white/15 px-2 py-1 text-white/70 hover:bg-white/[0.04] disabled:opacity-40"
              onClick={applyLastClose}
              disabled={!Number.isFinite(lastClose)}
            >
              帶入最後收盤 {Number.isFinite(lastClose) ? priceFmt(lastClose) : ""}
            </button>
            <button
              type="button"
              data-testid="risk-apply-atr-stop"
              className="rounded border border-white/15 px-2 py-1 text-white/70 hover:bg-white/[0.04] disabled:opacity-40"
              onClick={applyAtrStop}
              disabled={!Number.isFinite(atr14) || !Number.isFinite(toNumber(entry))}
            >
              ATR14 stop {Number.isFinite(atr14) ? `(${priceFmt(atr14)})` : ""}
            </button>
            {normalizedSymbol && bundle.isLoading ? (
              <span className="text-[var(--muted)]">載入 {normalizedSymbol} 報價…</span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded border border-white/10 bg-white/[0.02] p-3">
          <div className="card-title">每股 / 比率</div>
          <MetricRow
            label="每股風險"
            value={priceFmt(metrics.riskPerShare)}
            testId="risk-per-share"
          />
          <MetricRow
            label="每股獎酬"
            value={priceFmt(metrics.rewardPerShare)}
            testId="reward-per-share"
          />
          <MetricRow
            label="R / R"
            value={Number.isFinite(metrics.rr) ? metrics.rr.toFixed(2) : "—"}
            testId="risk-rr"
            sub={Number.isFinite(metrics.rr) && metrics.rr < 1 ? "獎酬 < 風險" : ""}
          />
          <MetricRow
            label="% 至 stop"
            value={Number.isFinite(metrics.pctToStop) ? `${(metrics.pctToStop * 100).toFixed(2)}%` : "—"}
          />
          <MetricRow
            label="% 至 target"
            value={
              Number.isFinite(metrics.pctToTarget) ? `${(metrics.pctToTarget * 100).toFixed(2)}%` : "—"
            }
          />
        </div>

        <div className="rounded border border-white/10 bg-white/[0.02] p-3">
          <div className="card-title">倉位 / 金額</div>
          <MetricRow
            label="建議股數"
            value={Number.isFinite(metrics.positionShares) ? metrics.positionShares.toLocaleString("en-US") : "—"}
            testId="risk-position-shares"
            sub="floor(預算 ÷ 每股風險)"
          />
          <MetricRow
            label="名目部位"
            value={moneyFmt(metrics.notional)}
            testId="risk-notional"
          />
          <MetricRow
            label="實際風險 $"
            value={moneyFmt(metrics.actualRiskDollars)}
            testId="risk-actual-dollars"
            sub={Number.isFinite(metrics.actualRiskDollars) && Number.isFinite(metrics.riskBudget)
              ? `預算 ${moneyFmt(metrics.riskBudget)}`
              : ""}
          />
        </div>
      </div>

      {metrics.issues.length > 0 ? (
        <ul data-testid="risk-issues" className="mt-3 space-y-1 text-[12px] text-amber-200/85">
          {metrics.issues.map((issue) => (
            <li key={issue}>• {issue}</li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="risk-submit-intent"
          className="rounded border border-emerald-500/30 bg-emerald-950/[0.12] px-3 py-1.5 text-[12px] font-semibold text-emerald-100/90 hover:bg-emerald-900/[0.18] disabled:opacity-40"
          onClick={handleSubmit}
          disabled={!metrics.canSubmit || !normalizedSymbol || createIntent.isPending}
        >
          {createIntent.isPending ? "送出中…" : "送入紙上 PENDING_REVIEW（不下單）"}
        </button>
        {submitNote ? (
          <span data-testid="risk-submit-note" className="text-[11px] text-[var(--muted)]">
            {submitNote}
          </span>
        ) : null}
      </div>
    </section>
  );
}
