import { useEffect, useState } from "react";

const STORAGE_KEY = "qsi_watchlist";
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

function writeWatchlist(items) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  } catch {
    /* ignore */
  }
}

export default function Watchlist() {
  const [items, setItems] = useState(() => readWatchlist());
  const [draft, setDraft] = useState("");

  useEffect(() => {
    writeWatchlist(items);
  }, [items]);

  const add = () => {
    const symbol = normalizeSymbol(draft);
    if (!symbol || items.includes(symbol) || items.length >= MAX_ITEMS) return;
    setItems((prev) => [...prev, symbol]);
    setDraft("");
  };

  const remove = (symbol) => {
    setItems((prev) => prev.filter((item) => item !== symbol));
  };

  return (
    <section className="card p-3" data-testid="portfolio-watchlist">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="card-title">Watchlist</div>
          <div className="text-[12px] text-[var(--muted)]">LocalStorage v1 · 最多 20 個代號</div>
        </div>
        <div className="flex min-w-[220px] flex-1 justify-end gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") add();
            }}
            className="min-w-0 rounded border border-white/15 bg-black/25 px-2 py-1.5 text-[13px] text-white"
            placeholder="新增代號"
            maxLength={16}
          />
          <button
            type="button"
            className="rounded bg-emerald-700 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-emerald-600"
            onClick={add}
          >
            Add
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
                className="text-white/50 hover:text-red-300"
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
