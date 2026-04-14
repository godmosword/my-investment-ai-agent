import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_URL ?? "";

/** Terminal `/terminal` 輪詢間隔（ms）；可由 `VITE_TERMINAL_POLL_MS` 覆寫，預設 45s，最小 5s、最大 5min。 */
export function getTerminalRefetchIntervalMs() {
  const raw = import.meta.env.VITE_TERMINAL_POLL_MS;
  if (raw === "" || raw === undefined || raw === null) return 45_000;
  const n = Number(raw);
  if (!Number.isFinite(n)) return 45_000;
  return Math.min(300_000, Math.max(5_000, Math.floor(n)));
}

/** 同頁多卡共用 snapshot 時，避免每卡獨立 refetchInterval（T3c）。 */
export function getTerminalQueryCoalesce() {
  const raw = import.meta.env.VITE_TERMINAL_QUERY_COALESCE;
  if (raw === "" || raw === undefined || raw === null) return true;
  return String(raw).trim() !== "0";
}

/** 同 ticker 多 hook 實例共用 staleTime（與輪詢間隔對齊，減少重複請求）。 */
export function getTerminalSharedStaleTimeMs() {
  const interval = getTerminalRefetchIntervalMs();
  return Math.min(interval, 120_000);
}

async function apiFetch(path) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  try {
    return await res.json();
  } catch (e) {
    throw new Error("Invalid JSON from API");
  }
}

async function apiPatchJson(path, body) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

export function useMetricsLatest() {
  return useQuery({
    queryKey: ["metrics", "latest"],
    queryFn: () => apiFetch("/api/metrics/latest"),
    staleTime: 5 * 60 * 1000, // 5 min
    retry: 1,
  });
}

export function useMetricsHistory(days = 30) {
  return useQuery({
    queryKey: ["metrics", "history", days],
    queryFn: () => apiFetch(`/api/metrics/history?days=${days}`),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

export function useReports(limit = 30) {
  return useQuery({
    queryKey: ["reports", limit],
    queryFn: () => apiFetch(`/api/reports?limit=${limit}`),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

export function useReport(date) {
  return useQuery({
    queryKey: ["report", date],
    queryFn: () => apiFetch(`/api/reports/${date}`),
    enabled: !!date,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}

export function useTrades(status, days = 60) {
  const params = new URLSearchParams({ days });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: ["trades", status, days],
    queryFn: () => apiFetch(`/api/trades?${params}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useTradesPerformance(days = 90) {
  return useQuery({
    queryKey: ["trades", "performance", days],
    queryFn: () => apiFetch(`/api/trades/performance?days=${days}`),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

export function useOpenPositions(days = 90) {
  return useQuery({
    queryKey: ["positions", "open", days],
    queryFn: () => apiFetch(`/api/positions/open?days=${days}`),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useWarRoomLatest(options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const coalesce = getTerminalQueryCoalesce();
  const refetchInterval = coalesce && livePoll ? interval * 1.05 : interval;
  return useQuery({
    queryKey: ["war-room", "latest", livePoll ? "live" : "static"],
    queryFn: () => apiFetch("/api/war-room/latest"),
    staleTime: livePoll ? Math.min(interval || 45_000, 60_000) : 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (/^5\d\d:/.test(msg)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(30_000, 1500 * 2 ** attempt),
  });
}

/**
 * @param {string} symbol
 * @param {number} [days]
 * @param {number} [recommendationLimit]
 * @param {{ livePoll?: boolean }} [options] — `livePoll: true` 時依 `VITE_TERMINAL_POLL_MS`（預設 45s）輪詢 snapshot（Terminal 頁）
 */
/**
 * Lightweight last / 1d change (M3); no BQ. Use with `livePoll: true` on Terminal cards.
 */
export function useSymbolQuote(symbol, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const coalesce = getTerminalQueryCoalesce();
  const refetchInterval = coalesce && livePoll ? interval * 1.1 : interval;
  const normalized = (symbol ?? "").trim().toUpperCase();
  const sharedStale = getTerminalSharedStaleTimeMs();
  return useQuery({
    queryKey: ["symbol", "quote", normalized, livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/symbols/${encodeURIComponent(normalized)}/quote`),
    enabled: !!normalized,
    staleTime: livePoll ? sharedStale : 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (/^5\d\d:/.test(msg)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(30_000, 1500 * 2 ** attempt),
  });
}

export function useSymbolSnapshot(symbol, days = 30, recommendationLimit = 12, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const coalesce = getTerminalQueryCoalesce();
  const refetchInterval = coalesce && livePoll ? interval * 1.15 : interval;
  const normalized = (symbol ?? "").trim().toUpperCase();
  const sharedStale = getTerminalSharedStaleTimeMs();
  return useQuery({
    queryKey: ["symbol", "snapshot", normalized, days, recommendationLimit, livePoll ? "live" : "static"],
    queryFn: () =>
      apiFetch(
        `/api/symbols/${encodeURIComponent(normalized)}/snapshot?days=${days}&recommendation_limit=${recommendationLimit}`,
      ),
    enabled: !!normalized,
    staleTime: livePoll ? sharedStale : 3 * 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (/^5\d\d:/.test(msg)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(30_000, 1500 * 2 ** attempt),
  });
}

export function useExecutionIntents(limit = 50, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const coalesce = getTerminalQueryCoalesce();
  const refetchInterval = coalesce && livePoll ? interval * 1.08 : interval;
  const status = options.statusFilter && options.statusFilter !== "all" ? String(options.statusFilter) : "";
  const category = options.categoryFilter && options.categoryFilter !== "all" ? String(options.categoryFilter) : "";
  const sortBy = options.sortBy || "updated_desc";
  const params = new URLSearchParams({ limit: String(limit), sort_by: sortBy });
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  return useQuery({
    queryKey: ["execution-intents", limit, sortBy, status || "all", category || "all", livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/execution-intents?${params}`),
    staleTime: livePoll ? Math.min(interval || 45_000, 60_000) : 2 * 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (/^5\d\d:/.test(msg)) return failureCount < 2;
      return failureCount < 1;
    },
    retryDelay: (attempt) => Math.min(30_000, 1500 * 2 ** attempt),
  });
}

export function useExecutionIntentAllowedStatuses() {
  return useQuery({
    queryKey: ["execution-intents", "allowed-statuses"],
    queryFn: () => apiFetch("/api/execution-intents/allowed-statuses"),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });
}

export function usePatchExecutionIntent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      signalId,
      status,
      note,
      reference_entry_price,
      reference_target_price,
      reference_stop_price,
    }) => {
      const enc = encodeURIComponent(signalId);
      return apiPatchJson(`/api/execution-intents/${enc}`, {
        status,
        note: note ?? "",
        reference_entry_price: reference_entry_price ?? null,
        reference_target_price: reference_target_price ?? null,
        reference_stop_price: reference_stop_price ?? null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution-intents"] });
      qc.invalidateQueries({ queryKey: ["war-room", "latest"] });
    },
  });
}
