import { useSymbolQuote } from "../../hooks/useApi";

const DEFAULT_SYMBOLS = ["BTC", "ETH", "SPY", "NVDA", "MSFT", "TSM"];

function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  if (Math.abs(value) >= 1) return value.toFixed(2);
  return value.toFixed(4);
}

function formatChange(value) {
  if (value == null || Number.isNaN(value)) return null;
  const sign = value > 0 ? "+" : value < 0 ? "" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function TickerCell({ symbol }) {
  const { data, isLoading, isError } = useSymbolQuote(symbol);

  const last = data?.last ?? data?.price ?? null;
  const changePct = data?.change_pct ?? data?.day_change_pct ?? null;
  const trendClass =
    typeof changePct === "number"
      ? changePct > 0
        ? "ticker-strip__chip--up"
        : changePct < 0
          ? "ticker-strip__chip--down"
          : ""
      : "";

  return (
    <span
      className={`ticker-strip__chip ${trendClass}`}
      data-testid="ticker-strip-chip"
      data-symbol={symbol}
    >
      <span className="ticker-strip__symbol">{symbol}</span>
      {isLoading ? (
        <span className="ticker-strip__price ticker-strip__price--muted">…</span>
      ) : isError || last == null ? (
        <span className="ticker-strip__price ticker-strip__price--muted">—</span>
      ) : (
        <span className="ticker-strip__price">{formatPrice(Number(last))}</span>
      )}
      {formatChange(changePct) ? (
        <span className="ticker-strip__change">{formatChange(changePct)}</span>
      ) : null}
    </span>
  );
}

/**
 * FE-2 — top-of-report compact ticker strip.
 * Mobile: horizontal scroll. Desktop: wraps. Data via existing useSymbolQuote
 * (no extra polling enabled; the hook coalesces stale time at 60s by default).
 */
export default function TickerStrip({ symbols = DEFAULT_SYMBOLS }) {
  const list = Array.isArray(symbols) && symbols.length ? symbols : DEFAULT_SYMBOLS;
  return (
    <div
      className="ticker-strip"
      role="region"
      aria-label="主要代號即時報價"
      data-testid="ticker-strip"
    >
      {list.map((sym) => (
        <TickerCell key={sym} symbol={sym} />
      ))}
    </div>
  );
}
