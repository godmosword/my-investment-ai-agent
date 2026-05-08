import { createContext, createElement, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { syncWarRoomRelatedQueries } from "./useApi";

const BASE = import.meta.env.VITE_API_URL ?? "";
const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";
const SSE_KEY = import.meta.env.VITE_SSE_STREAM_KEY ?? "";

const WarRoomSseStatusContext = createContext({ sseStatus: "idle" });

/**
 * App-wide SSE subscription to `/api/stream/war-room` (single EventSource, includes stream_key).
 * Children read status via `useWarRoomSseStatus` — do not open duplicate EventSources.
 */
export function WarRoomSseProvider({ children }) {
  const qc = useQueryClient();
  const [sseStatus, setSseStatus] = useState("idle");

  useEffect(() => {
    if (!SSE_ENABLED || !BASE) {
      setSseStatus("idle");
      return undefined;
    }

    const q = SSE_KEY ? `?stream_key=${encodeURIComponent(SSE_KEY)}` : "";
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
      syncWarRoomRelatedQueries(qc);
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

    es.onmessage = scheduleRefresh;
    es.onerror = () => setSseStatus("error");

    return () => {
      if (refreshTimer != null) {
        globalThis.clearTimeout(refreshTimer);
      }
      es.close();
    };
  }, [qc]);

  const value = useMemo(() => ({ sseStatus }), [sseStatus]);

  return createElement(WarRoomSseStatusContext.Provider, { value }, children);
}

export function useWarRoomSseStatus() {
  return useContext(WarRoomSseStatusContext);
}
