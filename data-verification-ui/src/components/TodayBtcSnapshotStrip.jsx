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
  const {
    data: snap,
    isLoading: sLoading,
    error: sErr,
    refetch: refetchSnap,
    isFetching: sFetching,
  } = useSymbolSnapshot("BTC", 30, 12, { livePoll: false });
  const {
    data: quote,
    isLoading: qLoading,
    error: qErr,
    refetch: refetchQuote,
    isFetching: qFetching,
  } = useSymbolQuote("BTC", { livePoll: false });

  const loading = sLoading || qLoading;
  const err = sErr || qErr;
  const line = formatQuoteLast(quote);
  const aligned = snap?.price_alignment?.aligned === true;
  const misaligned = snap?.price_alignment?.aligned === false;

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
        <div data-testid="today-btc-strip-status">
          <span style={{ color: "var(--red, #f87171)" }}>{err.message}</span>
          <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button
              type="button"
              className="war-room-retry"
              disabled={sFetching || qFetching}
              onClick={() => {
                void refetchSnap();
                void refetchQuote();
              }}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel)",
                color: "var(--text)",
                cursor: sFetching || qFetching ? "not-allowed" : "pointer",
              }}
            >
              {sFetching || qFetching ? "重試中…" : "重試載入"}
            </button>
          </div>
        </div>
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
          ) : misaligned ? (
            <span
              data-testid="today-btc-price-aligned"
              style={{ fontSize: 12, color: "var(--red, #f87171)", fontWeight: 600 }}
            >
              對齊警告：OHLC 與 quote 不一致
            </span>
          ) : (
            <span data-testid="today-btc-price-aligned" style={{ fontSize: 12, color: "var(--muted)" }}>
              對齊狀態：N/A
            </span>
          )}
          <button
            type="button"
            className="war-room-retry"
            disabled={sFetching || qFetching}
            onClick={() => {
              void refetchSnap();
              void refetchQuote();
            }}
            style={{
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--panel)",
              color: "var(--muted)",
              cursor: sFetching || qFetching ? "not-allowed" : "pointer",
            }}
          >
            重新整理
          </button>
        </div>
      )}
      {!loading && !err && misaligned ? (
        <div
          data-testid="today-btc-price-mismatch-banner"
          className="error-msg"
          style={{ marginTop: 10, fontSize: 12 }}
          role="alert"
        >
          後端回報 <code>price_alignment.aligned=false</code>：請以 Terminal「資料溯源」與後端欄位為準，勿將 headline 數字與圖表尾端視為已自動對齊。
        </div>
      ) : null}
    </div>
  );
}
