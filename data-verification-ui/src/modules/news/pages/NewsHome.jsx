import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { insightsSymbolHref } from "../../../constants/portalPhase4";
import { useNewsDeep, useNewsDigest, useNewsThemes } from "../../../hooks/useApi";

const FILTERS = [
  { id: "all", label: "全部", terms: [] },
  { id: "ai", label: "AI", terms: ["ai", "人工智慧", "gemini", "openai"] },
  { id: "semis", label: "半導體", terms: ["半導體", "semiconductor", "semis", "chip", "hbm"] },
  { id: "crypto", label: "加密", terms: ["加密", "crypto", "bitcoin", "btc", "ethereum"] },
  { id: "macro", label: "宏觀", terms: ["宏觀", "macro", "fed", "cpi", "dxy", "yield"] },
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

function pct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

function itemText(item) {
  return [
    item.headline,
    item.gemini_take,
    item.pillar,
    ...(Array.isArray(item.tags) ? item.tags : []),
  ]
    .join(" ")
    .toLowerCase();
}

function sourceLabel(item) {
  return item?.source_domain || item?.source_name || "來源待補";
}

function filterItems(items, filterId) {
  const filter = FILTERS.find((row) => row.id === filterId) ?? FILTERS[0];
  if (filter.id === "all") return items;
  return items.filter((item) => {
    const text = itemText(item);
    return filter.terms.some((term) => text.includes(term.toLowerCase()));
  });
}

function NewsItemButton({ item, active, onClick }) {
  const tags = Array.isArray(item.tags) ? item.tags.slice(0, 3) : [];
  return (
    <button
      type="button"
      data-testid="news-digest-item"
      className={`card w-full p-3 text-left transition hover:border-cyan-300/50 ${
        active ? "border-cyan-300/70 bg-cyan-950/[0.08]" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--muted)]">
        <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-cyan-200">
          {sourceLabel(item)}
        </span>
        <span>{formatTime(item.published_at)}</span>
        {tags.map((tag) => (
          <span key={tag} className="rounded bg-white/5 px-2 py-0.5 text-white/60">
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-2 text-[15px] font-semibold leading-snug text-white">{item.headline}</div>
      <p className="mt-2 text-[13px] leading-snug text-[var(--muted)]">
        {item.gemini_take || "Gemini take 待補。"}
      </p>
    </button>
  );
}

function ThemeRail({ themes }) {
  if (!themes.length) {
    return (
      <div className="card p-3">
        <div className="card-title">今日主軸</div>
        <div className="mt-2 text-[13px] text-[var(--muted)]">尚無主題聚合。</div>
      </div>
    );
  }
  return (
    <div className="card p-3">
      <div className="card-title">今日主軸</div>
      <div className="mt-3 space-y-2">
        {themes.slice(0, 8).map((theme) => (
          <div key={theme.id || theme.label} className="flex items-center justify-between gap-3 text-[13px]">
            <span className="text-white/80">{theme.label}</span>
            <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-[11px] text-cyan-200">
              {theme.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DeepPanel({ item, detail, loading, onClose }) {
  const current = detail || item;
  if (!current) return null;
  const thesis = Array.isArray(current.thesis_breakdown) ? current.thesis_breakdown : [];
  const tickers = Array.isArray(current.tickers) ? current.tickers : [];
  return (
    <aside
      data-testid="news-deep-panel"
      className="fixed inset-0 z-50 overflow-auto bg-[var(--bg,#05070a)] p-4 md:static md:z-auto md:max-h-none md:overflow-visible md:bg-transparent md:p-0"
    >
      <div className="card p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase text-cyan-200">Deep Brief</div>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug text-white">{current.headline}</h2>
          </div>
          <button
            type="button"
            className="rounded border border-white/15 px-2 py-1 text-[12px] text-white/70 hover:text-white"
            onClick={onClose}
          >
            關閉
          </button>
        </div>
        <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
          {current.source_url ? (
            <a className="text-cyan-200 hover:text-cyan-100" href={current.source_url} target="_blank" rel="noreferrer">
              {sourceLabel(current)}
            </a>
          ) : (
            <span className="text-cyan-200">{sourceLabel(current)}</span>
          )}
          <span>{formatTime(current.published_at)}</span>
          <span>信心 {pct(current.confidence)}</span>
        </div>
        {loading ? <div className="text-[13px] text-[var(--muted)]">載入 deep brief…</div> : null}
        <p className="text-[13px] leading-relaxed text-white/78">
          {current.deep_brief || current.gemini_take || "深度摘要待補。"}
        </p>
        <div className="mt-4">
          <div className="metric-label">論點拆解</div>
          <div className="mt-2 space-y-2">
            {(thesis.length ? thesis : [current.gemini_take || "尚無拆解"]).map((line) => (
              <div key={line} className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-white/75">
                {line}
              </div>
            ))}
          </div>
        </div>
        {tickers.length ? (
          <div className="mt-4">
            <div className="metric-label">相關標的（接續到觀點工作台）</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {tickers.map((ticker) => (
                <Link
                  key={ticker}
                  data-testid="news-ticker-to-insights"
                  className="min-h-[36px] rounded bg-amber-400/10 px-2 py-1 font-mono text-[12px] text-amber-200 hover:bg-amber-400/20"
                  to={insightsSymbolHref(ticker)}
                >
                  {String(ticker).toUpperCase()}
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function matchesFocus(item, focus) {
  if (!focus) return true;
  const f = focus.toLowerCase();
  const tickers = Array.isArray(item?.tickers) ? item.tickers : [];
  if (tickers.some((t) => String(t).toLowerCase() === f)) return true;
  return itemText(item).includes(f);
}

export default function NewsHome() {
  const [searchParams, setSearchParams] = useSearchParams();
  const focus = String(searchParams.get("focus") || "").trim().toUpperCase();
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const digestQuery = useNewsDigest({ limit: 25 });
  const themesQuery = useNewsThemes(80);
  const deepQuery = useNewsDeep(selected?.id);

  const items = useMemo(
    () =>
      (digestQuery.data?.items ?? []).filter(
        (item) => (item.source_domain || item.source_name) && item.headline,
      ),
    [digestQuery.data],
  );
  const filtered = useMemo(() => filterItems(items, filter), [items, filter]);
  const visibleItems = useMemo(
    () => (focus ? filtered.filter((item) => matchesFocus(item, focus)) : filtered),
    [filtered, focus],
  );

  const clearFocus = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("focus");
    setSearchParams(next, { replace: true });
  };
  const themes = themesQuery.data?.themes ?? digestQuery.data?.themes ?? [];

  const chooseFilter = (id) => {
    setFilter(id);
    setSelected(null);
  };

  return (
    <div data-testid="news-home" className="px-3 py-4 pb-24">
      <div className="page-header">
        <div className="page-title">科技即時報</div>
        <div className="page-subtitle">科技市場脈動與主題線索</div>
      </div>

      <div
        data-testid="news-reader-layer-intro"
        className="card mb-3 border border-white/10 bg-white/[0.03] p-3"
      >
        <div className="text-[12px] font-semibold text-white/90">讀者層 · 今天先看什麼？</div>
        <p className="mt-1 text-[12px] leading-relaxed text-[var(--muted)]">
          先以主題篩選與時間軸掃讀；需要標的深挖、紙上紀錄或訊號，再切到觀點工作台。
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Link
            to="/insights"
            data-testid="portal-cta-news-to-insights"
            className="inline-flex min-h-[36px] items-center rounded border border-emerald-500/30 bg-emerald-950/[0.12] px-3 py-1.5 text-[12px] font-semibold text-emerald-100/90 hover:bg-emerald-900/[0.18]"
          >
            去觀點工作台
          </Link>
          <Link
            to="/columns"
            data-testid="portal-cta-news-to-columns"
            className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
          >
            看深度專欄
          </Link>
        </div>
      </div>

      {focus ? (
        <div
          data-testid="news-focus-badge"
          className="card mb-3 flex flex-wrap items-center justify-between gap-2 border border-amber-300/25 bg-amber-400/[0.03] p-2 text-[12px] text-amber-100/90"
        >
          <span>
            聚焦標的：<span className="font-mono">{focus}</span>（由觀點工作台帶入）
          </span>
          <button
            type="button"
            data-testid="news-focus-clear"
            className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/75 hover:bg-white/5"
            onClick={clearFocus}
          >
            清除聚焦
          </button>
        </div>
      ) : null}

      <div className="mb-3 flex flex-wrap gap-2">
        {FILTERS.map((row) => (
          <button
            key={row.id}
            type="button"
            data-testid={`news-filter-${row.id}`}
            className={`rounded-full border px-3 py-1.5 text-[13px] ${
              filter === row.id
                ? "border-cyan-300/70 bg-cyan-400/[0.05] text-cyan-100"
                : "border-white/15 text-white/65 hover:text-white"
            }`}
            onClick={() => chooseFilter(row.id)}
          >
            {row.label}
          </button>
        ))}
      </div>

      {digestQuery.error ? (
        <div className="card mb-3 p-3 text-[13px] text-red-300" role="alert">
          科技即時報暫時無法載入。
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-2">
          {digestQuery.isLoading ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]">載入科技即時報…</div>
          ) : null}
          {!digestQuery.isLoading && visibleItems.length === 0 ? (
            <div className="card p-3 text-[13px] text-[var(--muted)]" role="status">
              尚無符合條件且具來源的新聞。
            </div>
          ) : null}
          {visibleItems.map((item) => (
            <NewsItemButton
              key={item.id}
              item={item}
              active={selected?.id === item.id}
              onClick={() => setSelected(item)}
            />
          ))}
        </section>

        <div className="space-y-3">
          <ThemeRail themes={themes} />
          {selected ? (
            <DeepPanel
              item={selected}
              detail={deepQuery.data}
              loading={deepQuery.isLoading}
              onClose={() => setSelected(null)}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
