import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { syncWarRoomRelatedQueries } from "./useApi";

const BASE = import.meta.env.VITE_API_URL ?? "";
const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";
const SSE_KEY = import.meta.env.VITE_SSE_STREAM_KEY ?? "";

/**
 * Single app-wide SSE subscription to `/api/stream/war-room`.
 * Keeps Today（War Room）、Terminal（execution intents）與後端推送同步而不重複連線。
 */
export function useWarRoomSse() {
  const qc = useQueryClient();

  useEffect(() => {
    if (!SSE_ENABLED || !BASE) return undefined;

    const q = SSE_KEY ? `?stream_key=${encodeURIComponent(SSE_KEY)}` : "";
    const url = `${BASE}/api/stream/war-room${q}`;
    let es;
    try {
      es = new EventSource(url);
    } catch {
      return undefined;
    }

    let refreshTimer = null;
    let lastRefreshAt = 0;

    const flushRefresh = () => {
      refreshTimer = null;
      lastRefreshAt = Date.now();
      syncWarRoomRelatedQueries(qc);
    };

    const scheduleRefresh = () => {
      const sinceLastRefresh = Date.now() - lastRefreshAt;
      if (sinceLastRefresh >= 1_000) {
        flushRefresh();
        return;
      }
      if (refreshTimer != null) return;
      refreshTimer = globalThis.setTimeout(flushRefresh, 1_000 - sinceLastRefresh);
    };

    es.onmessage = scheduleRefresh;
    es.onerror = () => {};

    return () => {
      if (refreshTimer != null) {
        globalThis.clearTimeout(refreshTimer);
      }
      es.close();
    };
  }, [qc]);
}
