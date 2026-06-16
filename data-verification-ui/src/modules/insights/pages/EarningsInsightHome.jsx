import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  columnsContextHref,
  ctaWithSymbol,
  insightsSymbolHref,
  newsContextHref,
  PORTAL_PHASE4_CTA,
  techPulseEarningsHref,
} from "../../../constants/portalPhase4";
import { useEarningsInsight, useEarningsUpcoming } from "../../../hooks/useApi";

const PILLAR_LABELS = {
  ai_silicon: "AI 矽晶",
  semiconductor: "半導體／記憶體",
  cloud_software: "雲端／軟體",
  hardware: "AI 伺服器／網通",
  optical: "光通訊",
  consumer_devices: "消費裝置",
  other: "其他",
};

function pillarLabel(pillar) {
  return PILLAR_LABELS[String(pillar || "other")] || "其他";
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
    }).format(new Date(`${iso}T00:00:00Z`));
  } catch {
    return iso;
  }
}

function CalendarRow({ item, active, onSelect }) {
  return (
    <button
      type="button"
      data-testid="earnings-calendar-row"
      data-symbol={item.symbol}
      className={`card flex w-full items-center justify-between gap-3 p-3 text-left transition hover:border-cyan-300/50 ${
        active ? "border-cyan-300/70 bg-cyan-950/[0.08]" : ""
      }`}
      onClick={() => onSelect(item.symbol)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[13px] font-semibold text-white">
          {item.symbol}
        </span>
        <span className="rounded border border-white/10 px-2 py-0.5 text-[11px] text-white/70">
          {pillarLabel(item.pillar)}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[12px]">
        <span className="text-white/85">{formatDate(item.next_earnings_date)}</span>
        <span className="font-mono text-cyan-200">D-{Math.max(0, item.days_until)}</span>
      </div>
    </button>
  );
}

function InsightPanel({ symbol, onClose }) {
  const query = useEarningsInsight(symbol);
  if (!symbol) return null;

  return (
    <aside data-testid="earnings-insight-panel" className="card p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase text-cyan-200">Filing Insight</div>
          <h2 className="mt-1 text-[18px] font-semibold text-white">{symbol}</h2>
        </div>
        <button
          type="button"
          className="rounded border border-white/15 px-2 py-1 text-[12px] text-white/70 hover:text-white"
          onClick={onClose}
        >
          關閉
        </button>
      </div>

      <div data-testid="earnings-symbol-fusion-cta" className="mb-3 flex flex-wrap gap-2">
        <Link
          to={insightsSymbolHref(symbol)}
          data-testid="earnings-cta-to-deep-dive"
          className="inline-flex min-h-[36px] items-center rounded border border-emerald-500/30 bg-emerald-950/[0.12] px-3 py-1.5 text-[12px] font-semibold text-emerald-100/90 hover:bg-emerald-900/[0.18]"
        >
          進入 {symbol} 深度頁
        </Link>
        <Link
          to={newsContextHref(symbol)}
          data-testid="earnings-cta-to-news"
          className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
        >
          {ctaWithSymbol(PORTAL_PHASE4_CTA.symbolToNews, symbol)}
        </Link>
        <Link
          to={columnsContextHref(symbol)}
          data-testid="earnings-cta-to-columns"
          className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
        >
          {ctaWithSymbol(PORTAL_PHASE4_CTA.symbolToColumns, symbol)}
        </Link>
        {techPulseEarningsHref(symbol) ? (
          <a
            href={techPulseEarningsHref(symbol)}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="earnings-cta-to-tech-pulse"
            className="inline-flex min-h-[36px] items-center rounded border border-cyan-500/30 bg-cyan-950/[0.12] px-3 py-1.5 text-[12px] font-semibold text-cyan-100/90 hover:bg-cyan-900/[0.18]"
          >
            {PORTAL_PHASE4_CTA.toTechPulseEarnings}
          </a>
        ) : null}
      </div>

      {query.isLoading ? (
        <div className="text-[13px] text-[var(--muted)]">載入財報 insight…</div>
      ) : null}
      {query.error ? (
        <div className="text-[13px] text-red-300" role="alert">
          財報 insight 無法載入：{query.error.message}
        </div>
      ) : null}

      {!query.isLoading && !query.error && query.data?.enabled === false ? (
        <div data-testid="earnings-insight-empty" className="rounded border border-white/10 bg-white/[0.03] p-3 text-[13px] text-[var(--muted)]">
          <div className="text-white/85">尚無 NotebookLM／agency 注入的財報 scaffold。</div>
          <div className="mt-1 text-[12px]">
            {query.data?.hint || "設定 DEEP_FILING_ANALYSIS_FILE 並 append JSONL 列。"}
          </div>
        </div>
      ) : null}

      {!query.isLoading && !query.error && query.data?.enabled === true ? (
        <div data-testid="earnings-insight-detail" className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
            <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-cyan-200">
              {query.data.analysis?.filing_type || "—"}
            </span>
            <span>as_of {query.data.as_of || "—"}</span>
          </div>

          {Object.entries(query.data.analysis?.answers ?? {}).map(([qid, answer]) => {
            const citations = query.data.analysis?.citations?.[qid] ?? [];
            return (
              <div key={qid} className="rounded border border-white/10 bg-white/[0.03] p-3">
                <div className="text-[12px] font-semibold text-cyan-200">Q{qid}</div>
                <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-white/80">
                  {answer}
                </p>
                {citations.length ? (
                  <div className="mt-2 space-y-1 text-[11px] text-white/55">
                    {citations.map((c, idx) => (
                      <div key={idx} className="rounded border border-white/10 px-2 py-1">
                        {c.excerpt || c.source || JSON.stringify(c)}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}

          {(query.data.analysis?.red_flags ?? []).length ? (
            <div className="rounded border border-amber-300/25 bg-amber-400/[0.03] p-3">
              <div className="text-[12px] font-semibold text-amber-100">Red Flags</div>
              <ul className="mt-1 list-disc pl-5 text-[12px] text-amber-100/90">
                {query.data.analysis.red_flags.map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

export default function EarningsInsightHome() {
  const [days, setDays] = useState(14);
  const [selected, setSelected] = useState(null);
  const upcoming = useEarningsUpcoming(days);
  const items = useMemo(() => upcoming.data?.items ?? [], [upcoming.data]);

  return (
    <div data-testid="earnings-insight-home" className="space-y-3">
      <div className="card border border-emerald-500/20 bg-emerald-950/[0.08] p-3 text-[12px] leading-relaxed text-white/80">
        <span className="font-semibold text-emerald-100/95">財報行事曆</span>
        ：未來 {days} 天大型科技與 AI 供應鏈財報日；點 ticker 看 NotebookLM／agency scaffold。
        資料源：yfinance 行事曆（內部快取 1 小時）；scaffold 由 DEEP_FILING_ANALYSIS_FILE 注入，無資料時明確標 enabled=false。
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {[7, 14, 30].map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`earnings-range-${n}`}
            className={`rounded border px-3 py-1 text-[12px] ${
              days === n
                ? "border-cyan-300/60 bg-cyan-400/[0.05] text-cyan-100"
                : "border-white/15 text-white/65 hover:text-white"
            }`}
            onClick={() => setDays(n)}
          >
            {n} 天
          </button>
        ))}
        <span className="ml-auto text-[11px] text-[var(--muted)]">
          watchlist {upcoming.data?.watchlist_size ?? "—"} 檔
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)]">
        <section className="space-y-2" data-testid="earnings-calendar-list">
          {upcoming.isLoading ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]">載入財報行事曆…</div>
          ) : null}
          {upcoming.error ? (
            <div className="card p-3 text-[13px] text-red-300" role="alert">
              財報行事曆暫時無法載入。
            </div>
          ) : null}
          {!upcoming.isLoading && !upcoming.error && items.length === 0 ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]" role="status">
              未來 {days} 天 watchlist 內未偵測到財報日（yfinance 行事曆可能延遲）。
            </div>
          ) : null}
          {items.map((item) => (
            <CalendarRow
              key={`${item.symbol}-${item.next_earnings_date}`}
              item={item}
              active={selected === item.symbol}
              onSelect={setSelected}
            />
          ))}
        </section>

        <div>
          {selected ? (
            <InsightPanel symbol={selected} onClose={() => setSelected(null)} />
          ) : (
            <div className="card p-3 text-[12px] text-[var(--muted)]">
              點左側 ticker 看 NotebookLM／agency 注入的財報 scaffold。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
