import { useMemo, useState } from "react";
import { useIndustryThemes, useNewsDeepList } from "../../../hooks/useApi";

const PILLARS = [
  { id: "ai", label: "AI", match: ["ai", "人工智慧", "llm", "openai", "gemini"] },
  { id: "semiconductor", label: "半導體", match: ["semiconductor", "semis", "chip", "hbm", "半導體", "先進封裝"] },
  { id: "crypto", label: "Crypto", match: ["crypto", "bitcoin", "btc", "ethereum", "eth", "加密", "區塊鏈"] },
];

function formatTime(value) {
  if (!value) return "時間待補";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function sourceLabel(item) {
  return item?.source_domain || item?.source_name || item?.source || "來源待補";
}

function titleOf(item) {
  return item?.title || item?.headline || "Untitled brief";
}

function summaryOf(item) {
  return item?.summary || item?.gemini_take || item?.deep_brief || item?.body || "摘要待補。";
}

function bodyOf(item) {
  return item?.body || item?.content || item?.deep_brief || item?.summary || item?.gemini_take || "Deep brief 待補。";
}

function readingMinutes(item) {
  const n = Number(item?.reading_minutes);
  if (Number.isFinite(n) && n > 0) return Math.ceil(n);
  const text = bodyOf(item);
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const words = (text.match(/[A-Za-z0-9]+/g) || []).length;
  return Math.max(1, Math.ceil(Math.max(cjk / 500, words / 220)));
}

function themeMatchesPillar(theme, pillar) {
  const text = [
    theme?.id,
    theme?.label,
    theme?.name,
    ...(Array.isArray(theme?.symbols) ? theme.symbols : []),
  ]
    .join(" ")
    .toLowerCase();
  return pillar.match.some((term) => text.includes(term.toLowerCase()));
}

function PillarTabs({ active, onChange }) {
  return (
    <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
      {PILLARS.map((pillar) => (
        <button
          key={pillar.id}
          type="button"
          data-testid={`columns-pillar-${pillar.id}`}
          className={`min-h-[44px] rounded-full border px-4 py-2 text-[13px] transition ${
            active === pillar.id
              ? "border-cyan-300/70 bg-cyan-400/10 text-cyan-100"
              : "border-white/15 text-white/65 hover:text-white"
          }`}
          onClick={() => onChange(pillar.id)}
        >
          {pillar.label}
        </button>
      ))}
    </div>
  );
}

function DeepBriefCard({ item, selected, onClick }) {
  const tickers = Array.isArray(item.tickers) ? item.tickers.slice(0, 4) : [];
  return (
    <button
      type="button"
      data-testid="columns-deep-card"
      className={`card w-full p-4 text-left transition hover:border-cyan-300/50 ${
        selected ? "border-cyan-300/70 bg-cyan-950/20" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--muted)]">
        <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-cyan-200">
          {sourceLabel(item)}
        </span>
        <span>{formatTime(item.published_at)}</span>
        <span>{readingMinutes(item)} min read</span>
      </div>
      <h2 className="mt-2 text-[16px] font-semibold leading-snug text-white">{titleOf(item)}</h2>
      <p className="mt-2 line-clamp-3 text-[13px] leading-relaxed text-[var(--muted)]">
        {summaryOf(item)}
      </p>
      {tickers.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {tickers.map((ticker) => (
            <span key={ticker} className="rounded bg-amber-400/10 px-2 py-1 font-mono text-[12px] text-amber-200">
              {ticker}
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function DeepBriefPanel({ item, onClose }) {
  if (!item) return null;
  const tickers = Array.isArray(item.tickers) ? item.tickers : [];
  const thesis = Array.isArray(item.thesis_breakdown) ? item.thesis_breakdown : [];
  return (
    <aside
      data-testid="columns-deep-panel"
      className="fixed inset-0 z-50 overflow-auto bg-[var(--bg,#05070a)] p-4 md:static md:z-auto md:overflow-visible md:bg-transparent md:p-0"
    >
      <div className="card p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase text-cyan-200">Deep Brief</div>
            <h2 className="mt-1 text-[18px] font-semibold leading-snug text-white">{titleOf(item)}</h2>
          </div>
          <button
            type="button"
            className="min-h-[44px] rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/70 hover:text-white"
            onClick={onClose}
          >
            關閉
          </button>
        </div>
        <div className="mb-4 flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
          {item.source_url ? (
            <a className="text-cyan-200 hover:text-cyan-100" href={item.source_url} target="_blank" rel="noreferrer">
              {sourceLabel(item)}
            </a>
          ) : (
            <span className="text-cyan-200">{sourceLabel(item)}</span>
          )}
          <span>{formatTime(item.published_at)}</span>
          <span>{readingMinutes(item)} min read</span>
        </div>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-white/78">{bodyOf(item)}</p>
        {thesis.length ? (
          <div className="mt-4">
            <div className="metric-label">論點拆解</div>
            <div className="mt-2 space-y-2">
              {thesis.map((line) => (
                <div key={line} className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white/75">
                  {line}
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {tickers.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {tickers.map((ticker) => (
              <a
                key={ticker}
                data-testid="columns-ticker-chip"
                className="min-h-[36px] rounded bg-amber-400/10 px-2 py-1 font-mono text-[12px] text-amber-200 hover:bg-amber-400/20"
                href={`/insights?symbol=${encodeURIComponent(String(ticker).toUpperCase())}`}
              >
                {String(ticker).toUpperCase()}
              </a>
            ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function RelatedThemes({ themes, activePillar }) {
  const pillar = PILLARS.find((row) => row.id === activePillar) || PILLARS[0];
  const related = useMemo(() => {
    const rows = Array.isArray(themes) ? themes : [];
    const exact = rows.filter((theme) => themeMatchesPillar(theme, pillar));
    return (exact.length ? exact : rows).slice(0, 6);
  }, [themes, pillar]);

  return (
    <div className="card p-4">
      <div className="card-title">相關主題</div>
      <div className="mt-3 space-y-2">
        {related.length ? (
          related.map((theme) => {
            const label = typeof theme === "string" ? theme : theme.label || theme.id || "—";
            const symbols = Array.isArray(theme?.symbols) ? theme.symbols : [];
            return (
              <div
                key={typeof theme === "string" ? theme : theme.id || label}
                data-testid="columns-theme-card"
                className="rounded border border-white/10 bg-white/[0.03] px-3 py-2"
              >
                <div className="text-[13px] font-medium text-white/85">{label}</div>
                {symbols.length ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {symbols.slice(0, 4).map((symbol) => (
                      <span key={symbol} className="font-mono text-[11px] text-cyan-200">
                        {symbol}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })
        ) : (
          <div className="text-[13px] text-[var(--muted)]">尚無相關主題卡。</div>
        )}
      </div>
    </div>
  );
}

export default function ColumnsHome() {
  const [activePillar, setActivePillar] = useState("ai");
  const [selected, setSelected] = useState(null);
  const deepQuery = useNewsDeepList({ pillar: activePillar, limit: 20 });
  const themesQuery = useIndustryThemes(80);
  const items = deepQuery.data?.items ?? [];

  const changePillar = (pillar) => {
    setActivePillar(pillar);
    setSelected(null);
  };

  return (
    <div data-testid="columns-home" className="px-3 py-4 pb-24">
      <div className="page-header">
        <div className="page-title">科技專欄</div>
        <div className="page-subtitle">Deep Briefs by pillar</div>
      </div>

      <PillarTabs active={activePillar} onChange={changePillar} />

      {deepQuery.error ? (
        <div className="card mb-3 p-3 text-[13px] text-red-300" role="alert">
          Deep Brief 暫時無法載入。
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-2">
          {deepQuery.isLoading ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]">載入 Deep Brief…</div>
          ) : null}
          {!deepQuery.isLoading && items.length === 0 ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]" role="status">
              此支柱暫無具來源的 Deep Brief。
            </div>
          ) : null}
          {items.map((item) => (
            <DeepBriefCard
              key={item.id}
              item={item}
              selected={selected?.id === item.id}
              onClick={() => setSelected(item)}
            />
          ))}
        </section>

        <div className="space-y-3">
          <RelatedThemes themes={themesQuery.data?.themes ?? []} activePillar={activePillar} />
          {selected ? <DeepBriefPanel item={selected} onClose={() => setSelected(null)} /> : null}
        </div>
      </div>
    </div>
  );
}
