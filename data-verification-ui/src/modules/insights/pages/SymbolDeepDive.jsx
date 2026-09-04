import { lazy, Suspense, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  columnsContextHref,
  ctaWithSymbol,
  newsContextHref,
  PORTAL_PHASE4_CTA,
} from "../../../constants/portalPhase4";
import { useAnalysisBundle, useExecutionIntents } from "../../../hooks/useApi";
import { finiteNumber } from "../../../utils/finiteNumber";
import { paperIntentMarkers } from "../paperIntentMarkers";

const SymbolCandleChart = lazy(() => import("../../../components/SymbolCandleChart"));

function formatPrice(value) {
  const n = finiteNumber(value);
  if (n == null) return "UNKNOWN";
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function presentOrUnknown(value) {
  if (value == null) return "UNKNOWN";
  const text = String(value).trim();
  return text ? text : "UNKNOWN";
}

function hasFilingPayload(value) {
  if (value == null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  const text = String(value).trim();
  const upper = text.toUpperCase();
  return text !== "" && upper !== "TEMPLATE" && upper !== "NULL";
}

function OptionalBlock({ title, value, testId }) {
  if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) return null;
  return (
    <div data-testid={testId} className="rounded border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[12px] font-semibold uppercase text-cyan-200">{title}</div>
      <div className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-white/70">
        {Array.isArray(value) ? value.join("\n") : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
      </div>
    </div>
  );
}

export default function SymbolDeepDive() {
  const symbol = useMemo(() => {
    try {
      return new URLSearchParams(globalThis.location?.search || "").get("symbol")?.trim().toUpperCase() || "";
    } catch {
      return "";
    }
  }, []);
  const query = useAnalysisBundle(symbol, 30, 12);
  const intentsQuery = useExecutionIntents(200);
  const paperMarkers = useMemo(
    () => paperIntentMarkers(intentsQuery.data, symbol),
    [intentsQuery.data, symbol],
  );
  if (!symbol) return null;

  const snapshot = query.data?.snapshot || {};
  const quote = query.data?.quote || {};
  const filing = snapshot.filing_summary || snapshot.filing || snapshot.filings;
  const notebook = snapshot.notebooklm || snapshot.notebooklm_notes || snapshot.notebook;
  const agency = snapshot.agency || snapshot.agency_notes || snapshot.agent_notes;
  const priceSeries = Array.isArray(snapshot.price_series) ? snapshot.price_series : [];

  return (
    <section data-testid="symbol-deep-dive" className="mb-3 rounded border border-cyan-300/20 bg-cyan-400/[0.02] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase text-cyan-200" data-testid="symbol-deep-dive-title">深度分析</div>
          <h1 className="mt-1 text-[20px] font-semibold text-white">{symbol}</h1>
        </div>
        <div className="text-right">
          <div className="text-[11px] uppercase text-[var(--muted)]" data-testid="symbol-last-label">最新價</div>
          <div className="font-mono text-[18px] font-semibold text-white" data-testid="symbol-last-price">{formatPrice(quote.last)}</div>
        </div>
      </div>

      <div data-testid="symbol-fusion-cta" className="mt-3 flex flex-wrap gap-2">
        <Link
          to={newsContextHref(symbol)}
          data-testid="symbol-cta-to-news"
          className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
        >
          {ctaWithSymbol(PORTAL_PHASE4_CTA.symbolToNews, symbol)}
        </Link>
        <Link
          to={columnsContextHref(symbol)}
          data-testid="symbol-cta-to-columns"
          className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
        >
          {ctaWithSymbol(PORTAL_PHASE4_CTA.symbolToColumns, symbol)}
        </Link>
      </div>

      <Suspense
        fallback={
          <div className="mt-3 text-[13px] text-[var(--muted)]" role="status">
            載入圖表…
          </div>
        }
      >
        <div className="mt-3" data-testid="deep-dive-candle-chart">
          <SymbolCandleChart symbol={symbol} priceSeries={priceSeries} eventMarkers={paperMarkers} />
        </div>
      </Suspense>
      {paperMarkers.length > 0 ? (
        <ul data-testid="deep-dive-paper-markers" className="mt-2 space-y-1 text-[12px] text-white/70">
          {paperMarkers.map((m) => (
            <li key={`${m.time}-${m.signal_id}`} data-testid="deep-dive-paper-marker">
              <span className="font-mono">{m.time}</span>
              {" · "}
              <span>{m.label}</span>
              {m.signal_id ? (
                <>
                  {" · "}
                  <span className="font-mono">{m.signal_id}</span>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <div data-testid="deep-dive-paper-markers-empty" className="mt-2 text-[12px] text-[var(--muted)]">
          暫無紙上訊號標記。
        </div>
      )}

      {query.isLoading ? <div className="mt-3 text-[13px] text-[var(--muted)]">載入分析資料…</div> : null}
      {query.error ? (
        <div className="mt-3 text-[13px] text-red-300" role="alert">
          Deep dive 無法載入：{query.error.message}
        </div>
      ) : null}
      {!query.isLoading && !query.error ? (
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <div className="rounded border border-white/10 bg-white/[0.03] p-3">
            <div className="text-[12px] font-semibold uppercase text-cyan-200">Snapshot</div>
            <div className="mt-2 text-[13px] text-white/70">
              Source: <span className="font-mono" data-testid="symbol-snapshot-source">{presentOrUnknown(snapshot.source)}</span>
            </div>
            <div className="mt-1 text-[13px] text-white/70">
              As of: <span className="font-mono" data-testid="symbol-snapshot-as-of">{presentOrUnknown(snapshot.as_of || quote.as_of)}</span>
            </div>
            {query.data?.snapshot_error ? (
              <div className="mt-2 text-[12px] text-amber-200">Snapshot warning: {query.data.snapshot_error}</div>
            ) : null}
          </div>
          {hasFilingPayload(filing) ? (
            <OptionalBlock title="Filing" value={filing} testId="symbol-filing-block" />
          ) : (
            <div
              data-testid="symbol-filing-empty"
              className="rounded border border-white/10 bg-white/[0.03] p-3 text-[13px] text-[var(--muted)]"
              role="status"
            >
              尚無本股財報摘要
            </div>
          )}
          <OptionalBlock title="NotebookLM" value={notebook} testId="symbol-notebook-block" />
          <OptionalBlock title="Agency" value={agency} testId="symbol-agency-block" />
        </div>
      ) : null}
    </section>
  );
}
