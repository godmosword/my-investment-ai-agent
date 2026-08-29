import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { insightsSymbolHref, PORTAL_PHASE4_GATE0 } from "../../../constants/portalPhase4";
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

function freshnessLabel(value) {
  if (value === "fresh") return "新鮮";
  if (value === "stale") return "過期";
  return "未知";
}

function freshnessClass(value) {
  if (value === "fresh") return "border-emerald-400/20 text-emerald-200/80";
  if (value === "stale") return "border-amber-400/20 text-amber-200/80";
  return "border-white/10 text-white/50";
}

function hasMissingQualityFields(item) {
  return Array.isArray(item?.missing_fields) && item.missing_fields.length > 0;
}

function titleOf(item) {
  return item?.title || item?.headline || "Untitled brief";
}

function aiInterpretation(value) {
  const text = String(value ?? "").trim();
  return text || "UNKNOWN／未提供";
}

function bodyOf(item) {
  return String(item?.body || item?.content || item?.deep_brief || "").trim();
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
              ? "border-cyan-300/70 bg-cyan-400/[0.05] text-cyan-100"
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
        selected ? "border-cyan-300/70 bg-cyan-950/[0.08]" : ""
      }`}
      onClick={onClick}
    >
      <div data-testid="reader-source-line" className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--muted)]">
        <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-cyan-200">
          {sourceLabel(item)}
        </span>
        <span>{formatTime(item.published_at)}</span>
        <span className={`rounded border px-2 py-0.5 ${freshnessClass(item.freshness)}`}>
          {freshnessLabel(item.freshness)}
        </span>
        {hasMissingQualityFields(item) ? (
          <span className="rounded border border-white/10 px-2 py-0.5 text-white/45">資料待補</span>
        ) : null}
        <span>{readingMinutes(item)} min read</span>
      </div>
      <h2 className="mt-2 text-[16px] font-semibold leading-snug text-white">{titleOf(item)}</h2>
      <div data-testid="columns-ai-interpretation" className="mt-2">
        <div className="text-[11px] font-semibold text-white/45">AI 解讀</div>
        <p className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-[var(--muted)]">
          {aiInterpretation(item.gemini_take)}
        </p>
      </div>
      {tickers.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {tickers.map((ticker) => (
            <Link
              key={ticker}
              data-testid="columns-card-ticker-to-insights"
              className="min-h-[36px] rounded bg-amber-400/10 px-2 py-1 font-mono text-[12px] text-amber-200 hover:bg-amber-400/20"
              to={insightsSymbolHref(ticker)}
            >
              {String(ticker).toUpperCase()}
            </Link>
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
  // Bilingual commentary (queue 45 P4): show language toggle only when both
  // sides exist. Falls back silently to the default body otherwise — we never
  // synthesize the missing language.
  const commentaryZh = String(item.commentary_zh || "").trim();
  const commentaryEn = String(item.commentary_en || "").trim();
  const hasBoth = Boolean(commentaryZh && commentaryEn);
  const [commentaryLang, setCommentaryLang] = useState("zh");
  const activeCommentary = commentaryLang === "en" ? commentaryEn : commentaryZh;
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
        <div data-testid="reader-source-line" className="mb-4 flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
          {item.source_url ? (
            <a className="text-cyan-200 hover:text-cyan-100" href={item.source_url} target="_blank" rel="noreferrer">
              {sourceLabel(item)}
            </a>
          ) : (
            <span className="text-cyan-200">{sourceLabel(item)}</span>
          )}
          <span>{formatTime(item.published_at)}</span>
          <span className={`rounded border px-2 py-0.5 text-[11px] ${freshnessClass(item.freshness)}`}>
            {freshnessLabel(item.freshness)}
          </span>
          {hasMissingQualityFields(item) ? (
            <span className="rounded border border-white/10 px-2 py-0.5 text-[11px] text-white/45">資料待補</span>
          ) : null}
          <span>{readingMinutes(item)} min read</span>
        </div>
        {commentaryZh || commentaryEn ? (
          <div data-testid="columns-commentary" className="mb-3">
            {hasBoth ? (
              <div className="mb-2 flex gap-1" data-testid="columns-commentary-toggle">
                {[
                  { id: "zh", label: "中" },
                  { id: "en", label: "EN" },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    data-testid={`columns-commentary-${opt.id}`}
                    className={`rounded border px-2 py-1 text-[11px] font-semibold ${
                      commentaryLang === opt.id
                        ? "border-emerald-500/40 bg-emerald-500/[0.08] text-emerald-100/90"
                        : "border-white/15 text-white/65 hover:bg-white/[0.04]"
                    }`}
                    onClick={() => setCommentaryLang(opt.id)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : null}
            <p
              data-testid="columns-commentary-text"
              className="whitespace-pre-wrap rounded border border-white/10 bg-white/[0.02] p-3 text-[13px] leading-relaxed text-white/80"
            >
              {activeCommentary || commentaryZh || commentaryEn}
            </p>
            {item.source_url ? (
              <div className="mt-1 text-[10px] text-[var(--muted)]">
                來源：
                <a
                  className="text-cyan-200/80 hover:text-cyan-100"
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {sourceLabel(item)}
                </a>{" "}
                · {formatTime(item.published_at)}（短評為翻譯／轉述；非原文）
              </div>
            ) : null}
          </div>
        ) : null}
        <div data-testid="columns-ai-interpretation" className="mb-3">
          <div className="text-[11px] font-semibold text-white/45">AI 解讀</div>
          <p className="mt-1 text-[13px] leading-relaxed text-white/78">{aiInterpretation(item.gemini_take)}</p>
        </div>
        {bodyOf(item) ? (
          <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-white/78">{bodyOf(item)}</p>
        ) : null}
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
              <Link
                key={ticker}
                data-testid="columns-ticker-chip"
                className="min-h-[36px] rounded bg-amber-400/10 px-2 py-1 font-mono text-[12px] text-amber-200 hover:bg-amber-400/20"
                to={insightsSymbolHref(ticker)}
              >
                {String(ticker).toUpperCase()}
              </Link>
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
                {theme?.thesis ? (
                  <div className="mt-1 text-[11px] leading-snug text-white/55">{theme.thesis}</div>
                ) : null}
                {symbols.length ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {symbols.slice(0, 4).map((symbol) => {
                      const ticker = String(symbol ?? "").trim();
                      if (!ticker) return null;
                      return (
                        <Link
                          key={ticker}
                          data-testid="columns-theme-symbol-to-insights"
                          className="font-mono text-[11px] text-cyan-200 hover:text-cyan-100"
                          to={insightsSymbolHref(ticker)}
                        >
                          {ticker.toUpperCase()}
                        </Link>
                      );
                    })}
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

function scoreColor(score) {
  const n = Number(score);
  if (!Number.isFinite(n) || n === 0) return "bg-white/10 text-white/60";
  if (n >= 3) return "bg-emerald-400/15 text-emerald-200";
  if (n > 0) return "bg-cyan-400/15 text-cyan-200";
  return "bg-red-400/15 text-red-200";
}

function SectorRotation({ rotation, source }) {
  const rows = Array.isArray(rotation) ? rotation.slice(0, 6) : [];
  return (
    <div className="card p-4" data-testid="columns-sector-rotation">
      <div className="flex items-center justify-between gap-2">
        <div className="card-title">Sector Rotation</div>
        <span className="text-[10px] text-[var(--muted)]">{source || "static"}</span>
      </div>
      <div className="mt-3 space-y-2">
        {rows.length ? rows.map((row) => {
          const score = Number(row.regime_score || 0);
          const width = `${Math.min(100, Math.max(8, Math.abs(score) * 22))}%`;
          return (
            <div key={row.id} data-testid="columns-rotation-row" className="rounded border border-white/10 bg-white/[0.03] p-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-[13px] font-semibold text-white/85">{row.label}</span>
                <span className={`rounded px-2 py-0.5 text-[11px] font-mono ${scoreColor(score)}`}>
                  {score >= 0 ? "+" : ""}{score}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded bg-white/10">
                <div className={score >= 0 ? "h-full bg-emerald-300/80" : "h-full bg-red-300/80"} style={{ width }} />
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {(row.symbols || []).slice(0, 4).map((symbol) => (
                  <Link
                    key={symbol}
                    to={insightsSymbolHref(symbol)}
                    className="font-mono text-[11px] text-cyan-200 hover:text-cyan-100"
                  >
                    {symbol}
                  </Link>
                ))}
              </div>
            </div>
          );
        }) : (
          <div className="text-[13px] text-[var(--muted)]">尚無 rotation 資料。</div>
        )}
      </div>
    </div>
  );
}

function columnsMatchFocus(item, focus) {
  if (!focus) return true;
  const f = focus.toLowerCase();
  const tickers = Array.isArray(item?.tickers) ? item.tickers : [];
  if (tickers.some((t) => String(t).toLowerCase() === f)) return true;
  const text = [titleOf(item), item?.summary, item?.gemini_take, item?.body, item?.content, item?.deep_brief]
    .join(" ")
    .toLowerCase();
  return text.includes(f);
}

export default function ColumnsHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const focus = String(searchParams.get("focus") || "").trim().toUpperCase();
  const [activePillar, setActivePillar] = useState("ai");
  const [selected, setSelected] = useState(null);
  const deepQuery = useNewsDeepList({ pillar: activePillar, limit: 20 });
  const themesQuery = useIndustryThemes(80);
  const rawItems = deepQuery.data?.items ?? [];
  const items = useMemo(
    () => (focus ? rawItems.filter((item) => columnsMatchFocus(item, focus)) : rawItems),
    [rawItems, focus],
  );

  const clearFocus = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("focus");
    setSearchParams(next, { replace: true });
  };

  const changePillar = (pillar) => {
    setActivePillar(pillar);
    setSelected(null);
  };

  return (
    <div data-testid="columns-home" className="px-3 py-4 pb-24">
      <div className="page-header">
        <div className="page-title">科技專欄</div>
        <div className="page-subtitle">深度敘事與支柱主題（讀者層）</div>
      </div>

      {focus ? (
        <div
          data-testid="columns-focus-badge"
          className="card mb-3 flex flex-wrap items-center justify-between gap-2 border border-amber-300/25 bg-amber-400/[0.03] p-2 text-[12px] text-amber-100/90"
        >
          <span>
            聚焦標的：<span className="font-mono">{focus}</span>（由觀點工作台帶入）
          </span>
          <button
            type="button"
            data-testid="columns-focus-clear"
            className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/75 hover:bg-white/5"
            onClick={clearFocus}
          >
            清除聚焦
          </button>
        </div>
      ) : null}

      <PillarTabs active={activePillar} onChange={changePillar} />

      {deepQuery.error ? (
        <div className="card mb-3 p-3 text-[13px] text-red-300" role="alert">
          Deep Brief 暫時無法載入。
        </div>
      ) : null}

      <div
        className={
          selected
            ? "md:grid md:grid-cols-[minmax(0,1fr)_minmax(20rem,28rem)] md:items-start md:gap-4"
            : undefined
        }
      >
        <section data-testid="columns-digest-stream" className="space-y-2">
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

        {selected ? (
          <div className="mt-3 md:sticky md:top-4 md:mt-0">
            <DeepBriefPanel item={selected} onClose={() => setSelected(null)} />
          </div>
        ) : null}
      </div>

      <details
        data-testid="columns-reader-layer-intro"
        className="card mt-4 border border-white/10 bg-white/[0.03] p-3"
      >
        <summary className="flex min-h-[36px] cursor-pointer list-none items-center text-[12px] font-semibold text-white/90">
          讀者層 · 長文與主軸
        </summary>
        <p className="mt-2 text-[12px] leading-relaxed text-[var(--muted)]">
          先選支柱、讀卡片摘要；若要查報價／部位／紙上流程，請到觀點工作台（目標路徑 ≤{" "}
          {PORTAL_PHASE4_GATE0.maxWorkbenchPathClicks} 次點擊）。
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Link
            to="/insights"
            data-testid="portal-cta-columns-to-insights"
            className="inline-flex min-h-[36px] items-center rounded border border-emerald-500/30 bg-emerald-950/[0.12] px-3 py-1.5 text-[12px] font-semibold text-emerald-100/90 hover:bg-emerald-900/[0.18]"
          >
            去觀點工作台
          </Link>
        </div>
      </details>

      <details className="mt-3">
        <summary className="card mb-2 flex min-h-[36px] cursor-pointer list-none items-center px-3 py-2 text-[13px] font-semibold text-white/85">
          板塊輪動與相關主題
        </summary>
        <div className="space-y-3">
          <SectorRotation rotation={themesQuery.data?.rotation ?? []} source={themesQuery.data?.source} />
          <RelatedThemes themes={themesQuery.data?.themes ?? []} activePillar={activePillar} />
        </div>
      </details>
    </div>
  );
}
