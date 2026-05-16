import { useComputeMemoryDashboard } from "../hooks/useApi";

function fmtUsd(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

function fmtUsdBn(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toFixed(digits)} B`;
}

function fmtPct(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function pctTone(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "text-white/60";
  if (n > 0) return "text-emerald-300/90";
  if (n < 0) return "text-red-300/90";
  return "text-white/60";
}

function SourceBadge({ live, source }) {
  const label = live ? "live" : source || "mock";
  return (
    <span
      data-testid="compute-memory-source-badge"
      className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
        live
          ? "border-emerald-400/40 text-emerald-200/90"
          : "border-amber-300/30 text-amber-200/85"
      }`}
    >
      {label}
    </span>
  );
}

function HbmDramBlock({ block }) {
  const items = Array.isArray(block?.items) ? block.items : [];
  return (
    <section data-testid="compute-memory-hbm-dram" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">HBM / DRAM 現貨</div>
          <div className="text-[11px] text-[var(--muted)]">
            as_of {block?.as_of || "—"} · {block?.note || "spot"}
          </div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">產品</th>
            <th className="py-1 text-left">規格</th>
            <th className="py-1 text-right">現貨 $</th>
            <th className="py-1 text-right">趨勢</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan="4" className="py-2 text-[11px] text-[var(--muted)]">
                fixture 為空。
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={`${row.product}-${row.spec}`} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.product}</td>
                <td className="py-1.5 text-white/65">{row.spec || "—"}</td>
                <td className="py-1.5 text-right font-mono text-white">{fmtUsd(row.spot_usd)}</td>
                <td className={`py-1.5 text-right font-mono ${pctTone(row.trend_pct)}`}>
                  {fmtPct(row.trend_pct)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

function CapexBlock({ block }) {
  const items = Array.isArray(block?.items) ? block.items : [];
  return (
    <section data-testid="compute-memory-capex" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">Hyperscaler Capex</div>
          <div className="text-[11px] text-[var(--muted)]">
            as_of {block?.as_of || "—"} · {block?.note || "quarterly"}
          </div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">Ticker</th>
            <th className="py-1 text-left">季度</th>
            <th className="py-1 text-right">Capex ($B)</th>
            <th className="py-1 text-right">YoY</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan="4" className="py-2 text-[11px] text-[var(--muted)]">
                fixture 為空。
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={`${row.ticker}-${row.quarter}`} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.ticker}</td>
                <td className="py-1.5 text-white/65">{row.quarter || "—"}</td>
                <td className="py-1.5 text-right font-mono text-white">{fmtUsdBn(row.capex_b_usd)}</td>
                <td className={`py-1.5 text-right font-mono ${pctTone(row.yoy_pct)}`}>
                  {fmtPct(row.yoy_pct)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

function GpuSpotBlock({ block }) {
  const items = Array.isArray(block?.items) ? block.items : [];
  return (
    <section data-testid="compute-memory-gpu-spot" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">GPU 現貨（hourly）</div>
          <div className="text-[11px] text-[var(--muted)]">
            as_of {block?.as_of || "—"} · {block?.note || "on-demand"}
          </div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">SKU</th>
            <th className="py-1 text-left">Provider</th>
            <th className="py-1 text-right">$ / hr</th>
            <th className="py-1 text-left">區域</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan="4" className="py-2 text-[11px] text-[var(--muted)]">
                fixture 為空。
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={`${row.sku}-${row.provider}`} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.sku}</td>
                <td className="py-1.5 text-white/65">{row.provider || "—"}</td>
                <td className="py-1.5 text-right font-mono text-white">{fmtUsd(row.hourly_usd)}</td>
                <td className="py-1.5 text-[11px] text-white/60">
                  {(Array.isArray(row.regions) && row.regions.length > 0 ? row.regions.join(", ") : "—")}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

export default function ComputeMemoryPanel() {
  const query = useComputeMemoryDashboard();
  const data = query.data;

  if (query.isLoading) {
    return (
      <section data-testid="compute-memory-panel" className="card mb-3 p-3 text-[12px] text-[var(--muted)]">
        載入算力／記憶體 dashboard…
      </section>
    );
  }
  if (query.error) {
    return (
      <section
        data-testid="compute-memory-panel"
        className="card mb-3 border border-red-400/30 p-3 text-[12px] text-red-300"
        role="alert"
      >
        無法載入算力／記憶體 dashboard：{query.error.message}
      </section>
    );
  }
  if (data?.enabled === false) {
    return (
      <section
        data-testid="compute-memory-panel"
        className="card mb-3 border border-amber-300/25 p-3 text-[12px] text-amber-100/85"
      >
        <div className="font-semibold">算力／記憶體 dashboard 尚未上線</div>
        <div className="mt-1 text-[11px] text-[var(--muted)]">
          原因：<code>{data?.reason || "unknown"}</code>。複製 <code>data/compute_memory_mock.json</code>{" "}
          或設定 <code>COMPUTE_MEMORY_FIXTURE_FILE</code>。
        </div>
      </section>
    );
  }

  return (
    <section data-testid="compute-memory-panel" className="card mb-3 border border-cyan-500/15 p-3">
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase text-cyan-200">算力 · 記憶體 · GPU 現貨</div>
          <div className="text-[11px] text-[var(--muted)]">
            as_of {data?.as_of || "—"}
          </div>
        </div>
        <SourceBadge live={data?.live} source={data?.live ? "live" : "mock"} />
      </header>
      {data?.disclaimer ? (
        <div
          data-testid="compute-memory-disclaimer"
          className="mb-2 rounded border border-amber-300/25 bg-amber-400/[0.03] p-2 text-[11px] text-amber-100/85"
        >
          {data.disclaimer}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <HbmDramBlock block={data?.hbm_dram_spot} />
        <CapexBlock block={data?.hyperscaler_capex} />
        <GpuSpotBlock block={data?.gpu_spot} />
      </div>
    </section>
  );
}
