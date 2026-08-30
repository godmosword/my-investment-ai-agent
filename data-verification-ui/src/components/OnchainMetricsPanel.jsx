import { useOnchainMetrics } from "../hooks/useApi";

const HONEST_EMPTY = "UNKNOWN：尚無真實資料";

function isLivePayload(live) {
  return live === true;
}

function isMockSource(source) {
  const s = String(source || "").toLowerCase();
  return s === "mock" || s === "fixture" || s === "placeholder";
}

function honestItems(block, live) {
  if (!isLivePayload(live)) return [];
  if (isMockSource(block?.source)) return [];
  return Array.isArray(block?.items) ? block.items : [];
}

function fmtNum(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function fmtUsd(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

function fmtUsdShort(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  return fmtUsd(n);
}

function fmtPct(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function flowTone(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "text-white/60";
  if (n > 0) return "text-red-300/90"; // inflow = sell-side risk
  if (n < 0) return "text-emerald-300/90";
  return "text-white/60";
}

function fundingTone(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "text-white/60";
  if (n > 5) return "text-amber-300/90";
  if (n < -5) return "text-amber-300/90";
  return "text-white/70";
}

function SourceBadge({ live, source }) {
  const label = live ? "live" : source || "mock";
  return (
    <span
      data-testid="onchain-source-badge"
      className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
        live ? "border-emerald-400/40 text-emerald-200/90" : "border-amber-300/30 text-amber-200/85"
      }`}
    >
      {label}
    </span>
  );
}

function BtcValuationBlock({ block, live }) {
  const items = honestItems(block, live);
  return (
    <section data-testid="onchain-btc-valuation" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">BTC 估值</div>
          <div className="text-[11px] text-[var(--muted)]">{block?.note || "MVRV-Z, realized price"}</div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">指標</th>
            <th className="py-1 text-right">值</th>
            <th className="py-1 text-left">解讀</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td
                colSpan="3"
                className="py-2 text-[11px] text-[var(--muted)]"
                data-testid="onchain-btc-valuation-empty"
                role="status"
              >
                {HONEST_EMPTY}
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={row.metric} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.metric}</td>
                <td className="py-1.5 text-right font-mono text-white">
                  {row.unit === "USD" ? fmtUsd(row.value) : fmtNum(row.value)}
                </td>
                <td className="py-1.5 text-[11px] text-white/60">{row.regime || row.note || "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

function ExchangeFlowBlock({ block, live }) {
  if (block?.enabled === false) {
    return (
      <section data-testid="onchain-exchange-flow" className="rounded border border-amber-300/25 bg-amber-400/[0.03] p-3">
        <header className="mb-2 flex items-center justify-between gap-2">
          <div>
            <div className="card-title">交易所淨流入</div>
            <div className="text-[11px] text-[var(--muted)]">CEX 淨流：無免費同級來源</div>
          </div>
          <SourceBadge source="disabled" />
        </header>
        <div className="rounded border border-white/10 bg-black/20 p-2 text-[12px] text-amber-100/85">
          無免費同級來源；CryptoQuant / Glassnode 付費資料仍為 pending。此區塊不使用 mock 淨流數字。
        </div>
        {block.reason ? <div className="mt-2 text-[11px] text-[var(--muted)]">reason: <code>{block.reason}</code></div> : null}
      </section>
    );
  }
  const items = honestItems(block, live);
  return (
    <section data-testid="onchain-exchange-flow" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">交易所淨流入</div>
          <div className="text-[11px] text-[var(--muted)]">{block?.note || "+inflow = sell-side"}</div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">場所</th>
            <th className="py-1 text-right">區間</th>
            <th className="py-1 text-right">淨流入 $</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td
                colSpan="3"
                className="py-2 text-[11px] text-[var(--muted)]"
                data-testid="onchain-exchange-flow-empty"
                role="status"
              >
                {HONEST_EMPTY}
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={row.venue} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.venue}</td>
                <td className="py-1.5 text-right text-white/60">{row.window_days ? `${row.window_days}d` : "—"}</td>
                <td className={`py-1.5 text-right font-mono ${flowTone(row.net_flow_usd)}`}>
                  {fmtUsdShort(row.net_flow_usd)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

function FundingRateBlock({ block, live }) {
  const items = honestItems(block, live);
  return (
    <section data-testid="onchain-funding-rate" className="rounded border border-white/10 bg-white/[0.02] p-3">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="card-title">永續資費（年化）</div>
          <div className="text-[11px] text-[var(--muted)]">{block?.note || ">5% 歷史過熱"}</div>
        </div>
        <SourceBadge source={block?.source} />
      </header>
      <table className="w-full text-[12px]">
        <thead className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
          <tr>
            <th className="py-1 text-left">資產</th>
            <th className="py-1 text-left">場所</th>
            <th className="py-1 text-right">APR</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td
                colSpan="3"
                className="py-2 text-[11px] text-[var(--muted)]"
                data-testid="onchain-funding-rate-empty"
                role="status"
              >
                {HONEST_EMPTY}
              </td>
            </tr>
          ) : (
            items.map((row) => (
              <tr key={`${row.asset}-${row.venue}`} className="border-t border-white/[0.04]">
                <td className="py-1.5 font-mono text-white/85">{row.asset}</td>
                <td className="py-1.5 text-white/60">{row.venue || "—"}</td>
                <td className={`py-1.5 text-right font-mono ${fundingTone(row.funding_apr_pct)}`}>
                  {fmtPct(row.funding_apr_pct)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

export default function OnchainMetricsPanel() {
  const query = useOnchainMetrics();
  const data = query.data;

  if (query.isLoading) {
    return (
      <section data-testid="onchain-panel" className="card mb-3 p-3 text-[12px] text-[var(--muted)]">
        <div data-testid="onchain-loading" role="status">
          載入 on-chain dashboard…
        </div>
      </section>
    );
  }
  if (query.error) {
    return (
      <section data-testid="onchain-panel" className="card mb-3 border border-red-400/30 p-3 text-[12px] text-red-300" role="alert">
        <div data-testid="onchain-error">無法載入 on-chain dashboard：{query.error.message}</div>
      </section>
    );
  }
  if (data?.enabled === false) {
    return (
      <section data-testid="onchain-panel" className="card mb-3 border border-amber-300/25 p-3 text-[12px] text-amber-100/85">
        <div data-testid="onchain-empty" role="status">
          {HONEST_EMPTY}
        </div>
      </section>
    );
  }

  return (
    <section data-testid="onchain-panel" className="card mb-3 border border-cyan-500/15 p-3">
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase text-cyan-200">Crypto · On-chain</div>
          <div className="text-[11px] text-[var(--muted)]">as_of {data?.as_of || "—"}</div>
        </div>
        <SourceBadge live={data?.live} source={data?.live ? "live" : "mock"} />
      </header>
      {data?.disclaimer ? (
        <div
          data-testid="onchain-disclaimer"
          className="mb-2 rounded border border-amber-300/25 bg-amber-400/[0.03] p-2 text-[11px] text-amber-100/85"
        >
          {data.disclaimer}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <BtcValuationBlock block={data?.btc_valuation} live={data?.live === true} />
        <ExchangeFlowBlock block={data?.exchange_flow} live={data?.live === true} />
        <FundingRateBlock block={data?.funding_rate} live={data?.live === true} />
      </div>
    </section>
  );
}
