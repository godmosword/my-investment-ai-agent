import { useEffect, useState } from "react";

const STORAGE_KEY = "qsi_watchlist";
const WATCHLIST_CHANGED_EVENT = "qsi_watchlist_changed";
const MAX_ITEMS = 20;

function normalizeSymbol(raw) {
  return String(raw ?? "").trim().toUpperCase().replace(/^\$/, "");
}

function readWatchlist() {
  try {
    const parsed = JSON.parse(globalThis.localStorage?.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return [...new Set(parsed.map(normalizeSymbol).filter(Boolean))].slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

function writeWatchlist(items, notify = false) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  } catch {
    /* ignore */
  }
  if (notify) {
    try {
      globalThis.dispatchEvent(new CustomEvent(WATCHLIST_CHANGED_EVENT));
    } catch {
      /* ignore */
    }
  }
}

export default function Watchlist({
  title = "觀察清單",
  description = "LocalStorage v1 · 最多 20 個代號",
  dataTestId = "portfolio-watchlist",
  compact = false,
} = {}) {
  const [items, setItems] = useState(() => readWatchlist());
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const sync = () => setItems(readWatchlist());
    globalThis.addEventListener(WATCHLIST_CHANGED_EVENT, sync);
    globalThis.addEventListener("storage", sync);
    return () => {
      globalThis.removeEventListener(WATCHLIST_CHANGED_EVENT, sync);
      globalThis.removeEventListener("storage", sync);
    };
  }, []);

  const add = () => {
    const symbol = normalizeSymbol(draft);
    if (!symbol || items.includes(symbol) || items.length >= MAX_ITEMS) return;
    const next = [...items, symbol].slice(0, MAX_ITEMS);
    writeWatchlist(next, true);
    setItems(next);
    setDraft("");
  };

  const remove = (symbol) => {
    const next = items.filter((item) => item !== symbol);
    writeWatchlist(next, true);
    setItems(next);
  };

  return (
    <section className="card p-3" data-testid={dataTestId}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="card-title" data-testid="watchlist-title">{title}</div>
          {description ? <div className="text-[12px] text-[var(--muted)]">{description}</div> : null}
        </div>
        <div className={`flex flex-1 justify-end gap-2 ${compact ? "min-w-full" : "min-w-[220px]"}`}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") add();
            }}
            className="min-h-[44px] min-w-0 rounded border border-white/15 bg-black/25 px-2 py-1.5 text-[13px] text-white"
            placeholder="新增代號"
            maxLength={16}
          />
          <button
            type="button"
            data-testid="watchlist-add"
            className="min-h-[44px] rounded bg-emerald-700 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-emerald-600"
            onClick={add}
          >
            新增
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="m-0 text-[13px] text-[var(--muted)]">尚無 watchlist 代號。</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map((symbol) => (
            <span
              key={symbol}
              className="inline-flex items-center gap-1 rounded border border-white/15 bg-white/5 px-2 py-1 font-mono text-[12px] text-white/85"
            >
              {symbol}
              <button
                type="button"
                data-testid="watchlist-remove"
                className="min-h-[44px] min-w-[44px] text-white/50 hover:text-red-300"
                onClick={() => remove(symbol)}
                aria-label={`移除 ${symbol}`}
              >
                x
              </button>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
