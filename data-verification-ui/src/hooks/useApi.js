import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_URL ?? "";

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

export function useWarRoomLatest() {
  return useQuery({
    queryKey: ["war-room", "latest"],
    queryFn: () => apiFetch("/api/war-room/latest"),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useSymbolSnapshot(symbol, days = 30, recommendationLimit = 12) {
  const normalized = (symbol ?? "").trim().toUpperCase();
  return useQuery({
    queryKey: ["symbol", "snapshot", normalized, days, recommendationLimit],
    queryFn: () =>
      apiFetch(
        `/api/symbols/${encodeURIComponent(normalized)}/snapshot?days=${days}&recommendation_limit=${recommendationLimit}`,
      ),
    enabled: !!normalized,
    staleTime: 3 * 60 * 1000,
    retry: 1,
  });
}
