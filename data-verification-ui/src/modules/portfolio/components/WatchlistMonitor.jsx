import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSymbolQuote } from "../../../hooks/useApi";
import OfflineBanner from "../../../components/OfflineBanner";

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

function writeWatchlist(items) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
    globalThis.dispatchEvent(new CustomEvent(WATCHLIST_CHANGED_EVENT));
  } catch {
    /* ignore */
  }
}

function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return "—";
  const n = Number(value);
  if (Math.abs(n) >= 1000) return n.toFixed(0);
  if (Math.abs(n) >= 1) return n.toFixed(2);
  return n.toFixed(4);
}

function formatChange(value) {
  if (value == null || Number.isNaN(value)) return null;
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function WatchlistRow({ symbol, onRemove, onOpen }) {
  const { data, isLoading, isError } = useSymbolQuote(symbol, { livePoll: true });
  const last = data?.last ?? data?.price ?? null;
  const changePct = data?.change_pct ?? data?.change_pct_1d ?? null;

  const trend =
    typeof changePct === "number" && changePct > 0
      ? "up"
      : typeof changePct === "number" && changePct < 0
        ? "down"
        : "flat";

  return (
    <li className="watchlist-monitor__row" data-testid="watchlist-monitor-row" data-symbol={symbol} data-trend={trend}>
      <button
        type="button"
        className="watchlist-monitor__open"
        onClick={() => onOpen(symbol)}
        aria-label={`開啟 ${symbol} 詳情`}
      >
        <span className="watchlist-monitor__symbol">{symbol}</span>
        <span className="watchlist-monitor__price">
          {isLoading ? "…" : isError || last == null ? "—" : formatPrice(Number(last))}
        </span>
        {formatChange(changePct) ? (
          <span className={`watchlist-monitor__change watchlist-monitor__change--${trend}`}>
            {formatChange(changePct)}
          </span>
        ) : null}
      </button>
      <button
        type="button"
        className="watchlist-monitor__remove"
        onClick={() => onRemove(symbol)}
        aria-label={`移除 ${symbol}`}
      >
        ×
      </button>
    </li>
  );
}

/**
 * FE-3 — row-style watchlist monitor with live quote, search filter, and
 * click-through to /insights?symbol=X (SymbolDeepDive). Shares storage with
 * the existing `Watchlist.jsx` chip view (`qsi_watchlist`).
 */
export default function WatchlistMonitor() {
  const [items, setItems] = useState(() => readWatchlist());
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

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
    writeWatchlist(next);
    setItems(next);
    setDraft("");
  };

  const remove = (symbol) => {
    const next = items.filter((item) => item !== symbol);
    writeWatchlist(next);
    setItems(next);
  };

  const openDetail = (symbol) => {
    navigate(`/insights?symbol=${encodeURIComponent(symbol)}`);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return items;
    return items.filter((s) => s.includes(q));
  }, [items, query]);

  return (
    <section className="watchlist-monitor card p-3" data-testid="watchlist-monitor">
      <OfflineBanner testId="watchlist-monitor-offline-banner" />
      <div className="watchlist-monitor__header">
        <div>
          <div className="card-title">Monitor</div>
          <div className="text-[12px] text-[var(--muted)]">
            即時報價（{import.meta.env.VITE_TERMINAL_POLL_MS ? `${import.meta.env.VITE_TERMINAL_POLL_MS}ms` : "45s"} 輪詢）· 點擊代號開啟深度頁
          </div>
        </div>
      </div>

      <div className="watchlist-monitor__toolbar">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜尋 watchlist…"
          className="watchlist-monitor__filter"
          data-testid="watchlist-monitor-filter"
          aria-label="搜尋 watchlist"
        />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value.toUpperCase())}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
          placeholder="新增代號"
          className="watchlist-monitor__add-input"
          maxLength={16}
          data-testid="watchlist-monitor-add-input"
        />
        <button
          type="button"
          onClick={add}
          className="watchlist-monitor__add-btn"
          data-testid="watchlist-monitor-add-btn"
        >
          Add
        </button>
      </div>

      {items.length === 0 ? (
        <p className="m-0 text-[13px] text-[var(--muted)]">尚無 watchlist 代號。新增後可即時觀察報價與漲跌。</p>
      ) : filtered.length === 0 ? (
        <p
          className="m-0 text-[13px] text-[var(--muted)]"
          data-testid="watchlist-monitor-empty-filtered"
        >
          沒有符合「{query}」的代號。
        </p>
      ) : (
        <ul className="watchlist-monitor__list" data-testid="watchlist-monitor-list">
          {filtered.map((symbol) => (
            <WatchlistRow key={symbol} symbol={symbol} onRemove={remove} onOpen={openDetail} />
          ))}
        </ul>
      )}
    </section>
  );
}
