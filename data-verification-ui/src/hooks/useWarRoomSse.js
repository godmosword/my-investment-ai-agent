import { createContext, createElement, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { syncWarRoomRelatedQueries } from "./useApi";
import { useSymbolFocus } from "../context/SymbolFocusContext";
import {
  TERMINAL_SSE_WATCH_CHANGED_EVENT,
  TERMINAL_SSE_WATCH_KEY,
} from "../constants/terminalStorage";

const BASE = import.meta.env.VITE_API_URL ?? "";
const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";
const SSE_KEY = import.meta.env.VITE_SSE_STREAM_KEY ?? "";

const WarRoomSseStatusContext = createContext({ sseStatus: "idle" });

function readWatchCsv() {
  try {
    return String(globalThis.localStorage?.getItem(TERMINAL_SSE_WATCH_KEY) ?? "").trim();
  } catch {
    return "";
  }
}

/** Up to 8 symbols for ``watch_symbols`` query (server truncates). */
function buildWatchSymbolsParam(focusSymbol) {
  const parts = [];
  const focus = (focusSymbol ?? "").trim().toUpperCase();
  if (focus) parts.push(focus);
  const extra = readWatchCsv()
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  for (const e of extra) {
    if (e && !parts.includes(e)) parts.push(e);
  }
  return parts.slice(0, 8).join(",");
}

/**
 * App-wide SSE subscription to `/api/stream/war-room` (single EventSource, includes stream_key).
 * Uses ``SymbolFocusProvider`` + ``localStorage`` (``TERMINAL_SSE_WATCH_KEY``) for ``watch_symbols``.
 * Children read status via `useWarRoomSseStatus` — do not open duplicate EventSources.
 */
export function WarRoomSseProvider({ children }) {
  const qc = useQueryClient();
  const { symbol } = useSymbolFocus();
  const [sseStatus, setSseStatus] = useState("idle");
  const [watchRev, setWatchRev] = useState(0);

  useEffect(() => {
    const bump = () => setWatchRev((r) => r + 1);
    globalThis.addEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
    globalThis.addEventListener("storage", bump);
    return () => {
      globalThis.removeEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
      globalThis.removeEventListener("storage", bump);
    };
  }, []);

  useEffect(() => {
    if (!SSE_ENABLED || !BASE) {
      setSseStatus("idle");
      return undefined;
    }

    const params = new URLSearchParams();
    if (SSE_KEY) params.set("stream_key", SSE_KEY);
    const watch = buildWatchSymbolsParam(symbol);
    if (watch) params.set("watch_symbols", watch);
    const q = params.toString() ? `?${params.toString()}` : "";
    const url = `${BASE}/api/stream/war-room${q}`;
    let es;
    try {
      es = new EventSource(url);
    } catch {
      setSseStatus("error");
      return undefined;
    }

    es.onopen = () => setSseStatus("connected");

    let refreshTimer = null;
    let lastRefreshAt = 0;

    const flushRefresh = () => {
      refreshTimer = null;
      lastRefreshAt = Date.now();
      syncWarRoomRelatedQueries(qc, { positionsListRefetchType: "none" });
    };

    const scheduleRefresh = () => {
      setSseStatus("connected");
      const sinceLastRefresh = Date.now() - lastRefreshAt;
      if (sinceLastRefresh >= 1_000) {
        flushRefresh();
        return;
      }
      if (refreshTimer != null) return;
      refreshTimer = globalThis.setTimeout(flushRefresh, 1_000 - sinceLastRefresh);
    };

    const onSymbolQuote = (ev) => {
      scheduleRefresh();
      try {
        const d = JSON.parse(ev.data);
        const sym = String(d?.symbol ?? "").trim().toUpperCase();
        if (sym) {
          qc.invalidateQueries({ queryKey: ["symbol", "quote", sym] });
        }
      } catch {
        /* ignore malformed */
      }
    };

    es.onmessage = scheduleRefresh;
    es.addEventListener("war_room_update", scheduleRefresh);
    es.addEventListener("symbol_quote", onSymbolQuote);
    es.onerror = () => setSseStatus("error");

    return () => {
      if (refreshTimer != null) {
        globalThis.clearTimeout(refreshTimer);
      }
      es.removeEventListener("symbol_quote", onSymbolQuote);
      es.close();
    };
  }, [qc, symbol, watchRev]);

  const value = useMemo(() => ({ sseStatus }), [sseStatus]);

  return createElement(WarRoomSseStatusContext.Provider, { value }, children);
}

export function useWarRoomSseStatus() {
  return useContext(WarRoomSseStatusContext);
}
