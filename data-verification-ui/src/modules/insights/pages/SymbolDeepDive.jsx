import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  columnsContextHref,
  ctaWithSymbol,
  newsContextHref,
  PORTAL_PHASE4_CTA,
} from "../../../constants/portalPhase4";
import { useAnalysisBundle } from "../../../hooks/useApi";

function formatPrice(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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
  if (!symbol) return null;

  const snapshot = query.data?.snapshot || {};
  const quote = query.data?.quote || {};
  const filing = snapshot.filing_summary || snapshot.filing || snapshot.filings;
  const notebook = snapshot.notebooklm || snapshot.notebooklm_notes || snapshot.notebook;
  const agency = snapshot.agency || snapshot.agency_notes || snapshot.agent_notes;

  return (
    <section data-testid="symbol-deep-dive" className="mb-3 rounded border border-cyan-300/20 bg-cyan-400/[0.04] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] uppercase text-cyan-200">Analysis Deep Dive</div>
          <h1 className="mt-1 text-[20px] font-semibold text-white">{symbol}</h1>
        </div>
        <div className="text-right">
          <div className="text-[11px] uppercase text-[var(--muted)]">Last</div>
          <div className="font-mono text-[18px] font-semibold text-white">{formatPrice(quote.last)}</div>
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
              Source: <span className="font-mono">{snapshot.source || "—"}</span>
            </div>
            <div className="mt-1 text-[13px] text-white/70">
              As of: <span className="font-mono">{snapshot.as_of || quote.as_of || "—"}</span>
            </div>
            {query.data?.snapshot_error ? (
              <div className="mt-2 text-[12px] text-amber-200">Snapshot warning: {query.data.snapshot_error}</div>
            ) : null}
          </div>
          <OptionalBlock title="Filing" value={filing} testId="symbol-filing-block" />
          <OptionalBlock title="NotebookLM" value={notebook} testId="symbol-notebook-block" />
          <OptionalBlock title="Agency" value={agency} testId="symbol-agency-block" />
        </div>
      ) : null}
    </section>
  );
}
