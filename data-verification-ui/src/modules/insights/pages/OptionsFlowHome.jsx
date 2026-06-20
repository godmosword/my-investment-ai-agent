import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useOptionsSummary, useOptionsGex, useOptionsFlow } from "../../../hooks/useApi";

const GexHistoryChart = lazy(() => import("../../../components/GexHistoryChart"));

/**
 * Insights「選擇權流」分頁：watchlist GEX 概覽 + 單標的 GEX 讀數與異常流。
 * 數字皆由後端（Python）算好注入；前端只渲染，缺料顯示 pending／等待狀態，不自算。
 * 三態：enabled:false（Polygon 未上線）／enabled:true 無資料（no_data_yet）／有資料。
 */

function formatGex(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
}

function regimeChipClass(regime) {
  if (regime === "positive") return "border-emerald-400/40 bg-emerald-500/[0.1] text-emerald-100/90";
  if (regime === "negative") return "border-rose-400/40 bg-rose-500/[0.1] text-rose-100/90";
  return "border-white/15 text-white/70";
}

function PendingCard({ payload }) {
  return (
    <div
      data-testid="options-pending"
      className="card border border-amber-400/20 bg-amber-950/[0.08] p-4 text-[13px] leading-relaxed text-white/80"
    >
      <div className="font-semibold text-amber-100/90">選擇權數據尚未上線</div>
      <p className="mt-1 text-white/70">
        Polygon Options 訂閱與每日管線就緒前，此處顯示等待狀態，不會捏造數字。
      </p>
      {payload?.hint ? <p className="mt-2 font-mono text-[11px] text-white/50">{payload.hint}</p> : null}
    </div>
  );
}

function WatchlistStrip({ items, selected, onSelect }) {
  return (
    <div data-testid="options-watchlist" className="mb-3 flex flex-wrap gap-2">
      {items.map((it) => (
        <button
          key={it.underlying}
          type="button"
          data-testid="options-watchlist-chip"
          data-symbol={it.underlying}
          aria-pressed={selected === it.underlying}
          onClick={() => onSelect(it.underlying)}
          className={`min-h-[44px] rounded border px-3 py-1.5 text-left text-[12px] ${
            selected === it.underlying ? "border-emerald-400/50 bg-emerald-500/[0.08]" : regimeChipClass(it.gex?.regime)
          }`}
        >
          <span className="font-mono font-semibold text-white">{it.underlying}</span>
          <span className="ml-2 text-white/70">
            GEX {it.gex ? formatGex(it.gex.total_gex) : "—"} · 異常 {it.unusual_count ?? 0}
          </span>
        </button>
      ))}
    </div>
  );
}

function GexReadout({ symbol }) {
  const { data, isLoading } = useOptionsGex(symbol);
  if (isLoading) return <div className="loading text-[13px] text-white/60">載入 GEX…</div>;
  if (data && data.enabled === false) return <PendingCard payload={data} />;
  const gex = data?.gex;
  if (!gex) {
    return (
      <div data-testid="options-gex-empty" className="card p-3 text-[13px] text-white/60">
        {symbol}：尚無 GEX 資料（等待管線首次執行）。
      </div>
    );
  }
  const regime = gex.regime || (Number(gex.total_gex) >= 0 ? "positive" : "negative");
  return (
    <div data-testid="options-gex-panel" className="card p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[14px] font-semibold text-white">{symbol}</span>
        <span className={`rounded border px-2 py-0.5 text-[11px] ${regimeChipClass(regime)}`}>
          {regime === "positive" ? "正 gamma（抑制波動）" : "負 gamma（放大波動）"}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-[12px]">
        <div>
          <div className="text-white/50">Total GEX</div>
          <div className="font-mono text-white">{formatGex(gex.total_gex)}</div>
        </div>
        <div>
          <div className="text-white/50">Call GEX</div>
          <div className="font-mono text-emerald-200/90">{formatGex(gex.call_gex)}</div>
        </div>
        <div>
          <div className="text-white/50">Put GEX</div>
          <div className="font-mono text-rose-200/90">{formatGex(gex.put_gex)}</div>
        </div>
      </div>
      {Array.isArray(data?.history) && data.history.length > 0 ? (
        <div className="mt-3 border-t border-white/5 pt-3">
          <Suspense fallback={<div className="loading text-[12px] text-white/50">載入圖表…</div>}>
            <GexHistoryChart history={data.history} />
          </Suspense>
        </div>
      ) : null}
    </div>
  );
}

function FlowList({ symbol }) {
  const { data, isLoading } = useOptionsFlow(symbol);
  if (isLoading) return <div className="loading text-[13px] text-white/60">載入異常流…</div>;
  if (data && data.enabled === false) return null;
  const signals = data?.signals || [];
  if (signals.length === 0) {
    return (
      <div data-testid="options-flow-empty" className="card p-3 text-[13px] text-white/60">
        {symbol}：近期無不尋常期權流訊號。
      </div>
    );
  }
  return (
    <div data-testid="options-flow-table" className="card p-3">
      <div className="mb-2 text-[12px] font-semibold text-white/80">近期不尋常期權流</div>
      <ul className="flex flex-col gap-2">
        {signals.map((s, i) => (
          <li
            key={`${s.option_ticker}-${i}`}
            data-testid="options-flow-row"
            className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2 text-[12px] last:border-0"
          >
            <span className="rounded border border-white/10 px-2 py-0.5 text-[11px] text-white/70">{s.signal_type}</span>
            <span className="font-mono text-white/85">{s.option_ticker}</span>
            <span className="text-white/60">{s.rationale}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function OptionsFlowHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const symbolQs = useMemo(() => String(searchParams.get("symbol") || "").trim().toUpperCase(), [searchParams]);
  const { data, isLoading, isError } = useOptionsSummary();
  const [selected, setSelected] = useState(symbolQs);

  const items = data?.items || [];
  useEffect(() => {
    if (!selected && items.length > 0) setSelected(items[0].underlying);
  }, [items, selected]);

  const onSelect = (sym) => {
    setSelected(sym);
    const next = new URLSearchParams(searchParams);
    next.set("symbol", sym);
    setSearchParams(next, { replace: true });
  };

  if (isLoading) return <div className="loading text-[13px] text-white/60">載入選擇權概覽…</div>;
  if (isError) return <div data-testid="options-error" className="card p-3 text-[13px] text-rose-200/80">無法載入選擇權資料。</div>;
  if (data && data.enabled === false) return <PendingCard payload={data} />;

  return (
    <div data-testid="options-flow-home">
      <WatchlistStrip items={items} selected={selected} onSelect={onSelect} />
      {selected ? (
        <div className="flex flex-col gap-3">
          <GexReadout symbol={selected} />
          <FlowList symbol={selected} />
        </div>
      ) : (
        <div className="card p-3 text-[13px] text-white/60">選一個標的查看 GEX 與異常流。</div>
      )}
    </div>
  );
}
