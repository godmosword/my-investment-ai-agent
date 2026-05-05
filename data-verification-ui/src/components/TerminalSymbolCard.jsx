import { Link } from "react-router-dom";
import { isHardApiError, useSymbolQuote, useSymbolSnapshot } from "../hooks/useApi";
import SymbolCandleChart from "./SymbolCandleChart";
import { useSymbolFocus } from "../context/SymbolFocusContext";
import AsOfChip from "./common/AsOfChip";
import ProvenancePopover from "./common/ProvenancePopover";

function numberOrDash(v, digits = 2) {
  if (v == null || Number.isNaN(Number(v))) return "N/A";
  return Number(v).toFixed(digits);
}

function alignmentTone(alignment) {
  if (!alignment) return { label: "對齊狀態：N/A", tone: "muted" };
  if (alignment.aligned === true) return { label: "對齊狀態：一致", tone: "ok" };
  if (alignment.aligned === false) return { label: "對齊警告：OHLC 與 quote 不一致", tone: "warn" };
  return {
    label: alignment.quote_error
      ? `對齊狀態：N/A（${alignment.quote_error}）`
      : "對齊狀態：N/A（後端未確認）",
    tone: "muted",
  };
}

export default function TerminalSymbolCard({
  symbol,
  onRemove,
  onMoveUp,
  onMoveDown,
  dragHandleProps,
}) {
  const {
    data,
    isLoading,
    error,
    isFetching,
    refetch: refetchSnapshot,
  } = useSymbolSnapshot(symbol, 30, 12, { livePoll: true });
  const {
    data: quote,
    isLoading: quoteLoading,
    error: quoteError,
    isFetching: quoteFetching,
    refetch: refetchQuote,
  } = useSymbolQuote(symbol, { livePoll: true });
  const { symbol: focusSymbol, setSymbol: setGlobalFocus } = useSymbolFocus();
  const isFocused = focusSymbol === symbol.toUpperCase();
  const hasSnapshot = Boolean(data);
  const blockingSnapshotError = Boolean(error && !hasSnapshot);
  const snapshotDegraded = Boolean(error && hasSnapshot);
  const quoteDegraded = Boolean(quoteError);
  const alignment = data?.price_alignment ?? null;
  const alignmentUi = alignmentTone(alignment);
  const quoteHardError = isHardApiError(quoteError);

  return (
    <div className="card terminal-card">
      <div className="terminal-card-header">
        <div className="terminal-card-title-wrap">
          <div className="card-title">Terminal · Symbol Snapshot</div>
          <div className="terminal-symbol">{symbol}</div>
        </div>
        <div className="terminal-card-actions">
          <button type="button" className="terminal-btn" onClick={onMoveUp}>
            ↑
          </button>
          <button type="button" className="terminal-btn" onClick={onMoveDown}>
            ↓
          </button>
          <button
            type="button"
            className="terminal-btn"
            onClick={() => setGlobalFocus(symbol)}
            title="寫入跨頁關注代號（localStorage）"
          >
            {isFocused ? "✓ 全域關注" : "設為全域關注"}
          </button>
          <button type="button" className="terminal-btn terminal-btn-danger" onClick={onRemove}>
            移除
          </button>
          <span className="terminal-drag-handle" {...dragHandleProps} title="拖曳重排">
            ⋮⋮
          </span>
        </div>
      </div>

      {isLoading && !hasSnapshot && <div className="loading">載入 {symbol} 快照中…</div>}
      {blockingSnapshotError && (
        <div className="error-msg" data-testid={`terminal-snapshot-error-${symbol}`}>
          {symbol} 載入失敗（<code>/api/symbols/{symbol}/snapshot</code>）：{error.message}
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="terminal-btn terminal-btn--small"
              disabled={isFetching}
              onClick={() => refetchSnapshot()}
            >
              {isFetching ? "重試中…" : "重試快照"}
            </button>
          </div>
        </div>
      )}
      {snapshotDegraded && (
        <div
          className="error-msg"
          style={{ marginBottom: 10 }}
          role="status"
          data-testid={`terminal-snapshot-degraded-${symbol}`}
        >
          <strong>{symbol} 快照暫時未更新。</strong> 保留上一筆成功資料顯示；請以最新重試結果為準。
          <div style={{ marginTop: 6, fontSize: 12, opacity: 0.95 }}>
            <code>/api/symbols/{symbol}/snapshot</code>：{error.message}
          </div>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              className="terminal-btn terminal-btn--small"
              disabled={isFetching}
              onClick={() => refetchSnapshot()}
            >
              {isFetching ? "重試中…" : "重試快照"}
            </button>
          </div>
        </div>
      )}

      {hasSnapshot && (
        <>
          <div style={{ marginBottom: 8 }}>
            <AsOfChip
              asOf={data.as_of}
              source={data.source ?? undefined}
              label="快照"
              polling={Boolean(isFetching)}
            />
          </div>

          {alignment?.aligned === false ? (
            <div
              className="error-msg"
              style={{ marginBottom: 10, fontSize: 12 }}
              role="alert"
              data-testid={`terminal-price-mismatch-banner-${symbol}`}
            >
              <strong>價格對齊警告</strong>：日線 OHLC 尾端與 <code>/quote</code> 最新收盤不一致（相對差{" "}
              {alignment.rel_diff != null
                ? `${(Number(alignment.rel_diff) * 100).toFixed(3)}%`
                : "N/A"}
              ）。請以「資料溯源」與後端 <code>price_alignment</code> 為準；圖表與 headline 數字可能不同步。
              {alignment?.e2e_override ? (
                <span>
                  {" "}
                  （<code>E2E</code> 覆寫）
                </span>
              ) : null}
              <div style={{ marginTop: 6, fontSize: 11, opacity: 0.95 }}>
                儀表 KPI（<code>latest_metrics</code>）來源為 BigQuery；本警告僅涵蓋 yfinance 之 OHLC 尾端 vs <code>/quote</code>。
              </div>
              {quoteError ? (
                <div style={{ marginTop: 6 }}>
                  <button
                    type="button"
                    className="terminal-btn terminal-btn--small"
                    disabled={quoteFetching}
                    onClick={() => refetchQuote()}
                  >
                    {quoteFetching ? "重試 quote…" : "重試 quote"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          {alignment?.aligned !== false ? (
            <div
              className={alignmentUi.tone === "ok" ? "page-subtitle" : "page-subtitle"}
              style={{
                marginBottom: 10,
                fontSize: 12,
                color:
                  alignmentUi.tone === "ok"
                    ? "var(--green, #4ade80)"
                    : "var(--muted)",
              }}
              data-testid={`terminal-price-alignment-status-${symbol}`}
            >
              {alignmentUi.label}。請以「資料溯源」與後端欄位為準。
            </div>
          ) : null}
          {quoteDegraded ? (
            <div
              className="error-msg"
              style={{ marginBottom: 10, fontSize: 12 }}
              role="status"
              data-testid={`terminal-quote-degraded-${symbol}`}
            >
              <strong>{symbol} quote 暫時未更新。</strong>{" "}
              {quoteHardError ? "目前視為 hard error。" : "保留快照內容，稍後可再重試。"}
              <div style={{ marginTop: 6 }}>
                <code>/api/symbols/{symbol}/quote</code>：{quoteError.message}
              </div>
            </div>
          ) : null}

          <div className="terminal-quote-strip">
            {quoteLoading && !quote ? (
              <span className="terminal-quote-muted">最新價載入中…</span>
            ) : quoteError ? (
              <span className="terminal-quote-muted" title={quoteError.message}>
                最新價：無法取得（<code>/api/symbols/{symbol}/quote</code>）
                <button
                  type="button"
                  className="terminal-btn terminal-btn--small"
                  style={{ marginLeft: 8, verticalAlign: "middle" }}
                  disabled={quoteFetching}
                  onClick={() => refetchQuote()}
                >
                  {quoteFetching ? "…" : "重試"}
                </button>
              </span>
            ) : quote && quote.last != null ? (
              <>
                <span className="terminal-quote-label">最新收盤（日線）</span>
                <span className="terminal-quote-last" data-testid={`terminal-quote-last-${symbol}`}>
                  {quote.last != null ? Number(quote.last).toLocaleString("en-US", { maximumFractionDigits: 6 }) : "—"}
                  {quote.currency ? ` ${quote.currency}` : ""}
                </span>
                {quote.change_pct_1d != null ? (
                  <span
                    className={
                      Number(quote.change_pct_1d) >= 0 ? "terminal-quote-chg-up" : "terminal-quote-chg-down"
                    }
                  >
                    {Number(quote.change_pct_1d) >= 0 ? "+" : ""}
                    {Number(quote.change_pct_1d).toFixed(2)}%（1D）
                  </span>
                ) : null}
                <span className="terminal-quote-asof">
                  bar {quote.as_of ? new Date(quote.as_of).toLocaleDateString("zh-TW") : "—"}
                  {quote.cached ? " · 快取" : ""}
                  {quoteFetching ? " · 更新中" : ""}
                </span>
              </>
            ) : (
              <span className="terminal-quote-muted">最新價：無資料</span>
            )}
          </div>
          <ProvenancePopover provenance={data.data_provenance} />
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Risk / 5</div>
              <div className="metric-value">{numberOrDash(data.latest_metrics?.avg_risk_score, 1)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">MVRV Z</div>
              <div className="metric-value">{numberOrDash(data.latest_metrics?.mvrv_z_score, 2)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Sentiment</div>
              <div className="metric-value">{numberOrDash(data.latest_metrics?.sentiment_score, 3)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">DXY</div>
              <div className="metric-value">{numberOrDash(data.latest_metrics?.dxy, 2)}</div>
            </div>
          </div>

          <SymbolCandleChart
            symbol={symbol}
            priceSeries={Array.isArray(data.price_series) ? data.price_series : []}
            eventMarkers={Array.isArray(data.event_markers) ? data.event_markers : []}
          />

          <div className="section-header subtle">最近事件（QSREC）</div>
          {Array.isArray(data.event_markers) && data.event_markers.length > 0 ? (
            <div className="terminal-event-list">
              {data.event_markers.slice(0, 5).map((e, idx) => (
                <div key={`${e.time}-${idx}`} className="terminal-event-item">
                  <span>{e.time}</span>
                  <strong>{e.label}</strong>
                  <span>
                    entry {e.entry_price ?? "N/A"} / target {e.target_price ?? "N/A"} / stop{" "}
                    {e.stop_price ?? "N/A"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="page-subtitle">暫無事件標註。</div>
          )}

          {Array.isArray(data.report_links) && data.report_links.length > 0 && (
            <>
              <div className="section-header subtle">關聯報告</div>
              <div className="terminal-report-links" data-testid={`terminal-report-links-${symbol}`}>
                {data.report_links.map((link) => {
                  const href = link.href || "";
                  const internal = href.startsWith("/report/");
                  return internal ? (
                    <Link key={link.href || link.report_date} to={href}>
                      {link.report_date}
                    </Link>
                  ) : (
                    <a key={link.href || link.report_date} href={href} target="_blank" rel="noreferrer">
                      {link.report_date}
                    </a>
                  );
                })}
                <Link className="terminal-report-links-today" to="/today" data-testid={`terminal-today-link-${symbol}`}>
                  今日戰情室
                </Link>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
