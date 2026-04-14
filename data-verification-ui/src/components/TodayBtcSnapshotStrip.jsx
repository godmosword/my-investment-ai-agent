import { useSymbolQuote, useSymbolSnapshot } from "../hooks/useApi";

function formatQuoteLast(quote) {
  if (!quote || quote.last == null) return null;
  const n = Number(quote.last).toLocaleString("en-US", { maximumFractionDigits: 6 });
  return quote.currency ? `${n} ${quote.currency}` : n;
}

/**
 * E2E / Bloomberg §6：與 Terminal 卡同源 API，顯示 BTC 最新收盤（與 snapshot OHLC 對齊由後端 price_alignment 保證）。
 */
export default function TodayBtcSnapshotStrip() {
  const { data: snap, isLoading: sLoading, error: sErr } = useSymbolSnapshot("BTC", 30, 12, { livePoll: false });
  const { data: quote, isLoading: qLoading, error: qErr } = useSymbolQuote("BTC", { livePoll: false });

  const loading = sLoading || qLoading;
  const err = sErr || qErr;
  const line = formatQuoteLast(quote);
  const aligned = snap?.price_alignment?.aligned === true;

  return (
    <div
      className="card"
      style={{ marginBottom: 14, padding: "10px 12px", fontSize: 13 }}
      data-testid="today-btc-snapshot-strip"
    >
      <div className="section-header subtle" style={{ marginBottom: 6 }}>
        BTC 即時對照（Terminal 同源 API）
      </div>
      {loading && (
        <span data-testid="today-btc-strip-status" style={{ color: "var(--muted)" }}>
          載入中…
        </span>
      )}
      {!loading && err && (
        <span data-testid="today-btc-strip-status" style={{ color: "var(--red, #f87171)" }}>
          {err.message}
        </span>
      )}
      {!loading && !err && line && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "baseline" }}>
          <span style={{ color: "var(--muted)" }}>最新收盤（日線）</span>
          <span
            data-testid="today-btc-quote-last"
            style={{ fontFamily: "ui-monospace, monospace", fontWeight: 600, color: "var(--text)" }}
          >
            {line}
          </span>
          {aligned ? (
            <span data-testid="today-btc-price-aligned" style={{ fontSize: 12, color: "var(--green, #4ade80)" }}>
              與 snapshot OHLC 尾端一致
            </span>
          ) : (
            <span data-testid="today-btc-price-aligned" style={{ fontSize: 12, color: "var(--muted)" }}>
              對齊狀態：{snap?.price_alignment?.aligned === false ? "待查" : "N/A"}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
