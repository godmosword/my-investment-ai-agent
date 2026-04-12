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
  return useQuery({
    queryKey: ["war-room", "latest", livePoll ? "live" : "static"],
    queryFn: () => apiFetch("/api/war-room/latest"),
    staleTime: livePoll ? Math.min(interval, 60_000) : 60 * 1000,
    refetchInterval: interval,
    retry: 1,
  });
}

/**
 * @param {string} symbol
 * @param {number} [days]
 * @param {number} [recommendationLimit]
 * @param {{ livePoll?: boolean }} [options] — `livePoll: true` 時依 `VITE_TERMINAL_POLL_MS`（預設 45s）輪詢 snapshot（Terminal 頁）
 */
export function useSymbolSnapshot(symbol, days = 30, recommendationLimit = 12, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const normalized = (symbol ?? "").trim().toUpperCase();
  return useQuery({
    queryKey: ["symbol", "snapshot", normalized, days, recommendationLimit, livePoll ? "live" : "static"],
    queryFn: () =>
      apiFetch(
        `/api/symbols/${encodeURIComponent(normalized)}/snapshot?days=${days}&recommendation_limit=${recommendationLimit}`,
      ),
    enabled: !!normalized,
    staleTime: livePoll ? Math.min(interval, 120_000) : 3 * 60 * 1000,
    refetchInterval: interval,
    retry: 1,
  });
}

export function useExecutionIntents(limit = 50, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  return useQuery({
    queryKey: ["execution-intents", limit, livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/execution-intents?limit=${limit}`),
    staleTime: livePoll ? Math.min(interval, 60_000) : 2 * 60 * 1000,
    refetchInterval: interval,
    retry: 1,
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
    mutationFn: async ({ signalId, status, note }) => {
      const enc = encodeURIComponent(signalId);
      return apiPatchJson(`/api/execution-intents/${enc}`, { status, note: note ?? "" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution-intents"] });
      qc.invalidateQueries({ queryKey: ["war-room", "latest"] });
    },
  });
}
