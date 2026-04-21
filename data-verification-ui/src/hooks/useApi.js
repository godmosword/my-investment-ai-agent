import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_URL ?? "";

function isServerErrorMessage(message) {
  return /^5\d\d:/.test(String(message ?? ""));
}

export function isHardApiError(error) {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (message.startsWith("Invalid JSON")) return true;
  if (/^4\d\d:/.test(message)) return true;
  return !isServerErrorMessage(message);
}

function getE2eFlag(key) {
  if (import.meta.env.VITE_E2E !== "1") return "";
  try {
    return String(globalThis.localStorage?.getItem(key) ?? "").trim();
  } catch {
    return "";
  }
}

function symbolInCsvFlag(raw, symbol) {
  const sym = String(symbol ?? "").trim().toUpperCase();
  if (!raw || !sym) return false;
  return raw
    .split(",")
    .map((part) => part.trim().toUpperCase())
    .filter(Boolean)
    .includes(sym);
}

function e2eSymbolQuery(symbol, endpoint) {
  if (import.meta.env.VITE_E2E !== "1") return "";
  const sym = String(symbol ?? "").trim().toUpperCase();
  const params = new URLSearchParams();

  if (sym === "BTC" && getE2eFlag("e2e_btc_misaligned") === "1") {
    params.set("e2e_btc_misaligned", "1");
  }
  if (sym === "BTC" && getE2eFlag("e2e_btc_alignment_na") === "1") {
    params.set("e2e_btc_alignment_na", "1");
  }

  if (endpoint === "snapshot" && symbolInCsvFlag(getE2eFlag("e2e_snapshot_fail_symbols"), sym)) {
    params.set("e2e_snapshot_fail", "1");
  }
  if (endpoint === "quote" && symbolInCsvFlag(getE2eFlag("e2e_quote_fail_symbols"), sym)) {
    params.set("e2e_quote_fail", "1");
  }

  const qstr = params.toString();
  return qstr ? `?${qstr}` : "";
}

/** Terminal `/terminal` 輪詢間隔（ms）；可由 `VITE_TERMINAL_POLL_MS` 覆寫，預設 45s，最小 5s、最大 5min。 */
export function getTerminalRefetchIntervalMs() {
  const raw = import.meta.env.VITE_TERMINAL_POLL_MS;
  if (raw === "" || raw === undefined || raw === null) return 45_000;
  const n = Number(raw);
  if (!Number.isFinite(n)) return 45_000;
  return Math.min(300_000, Math.max(5_000, Math.floor(n)));
}

/** 同頁多卡共用 snapshot 時，避免每卡獨立 refetchInterval（T3c）。 */
function getTerminalQueryCoalesce() {
  const raw = import.meta.env.VITE_TERMINAL_QUERY_COALESCE;
  if (raw === "" || raw === undefined || raw === null) return true;
  return String(raw).trim() !== "0";
}

/** 同 ticker 多 hook 實例共用 staleTime（與輪詢間隔對齊，減少重複請求）。 */
function getTerminalSharedStaleTimeMs() {
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

/**
 * @param {number} [limit]
 * @param {string | null | undefined} [profile] — 與 `GET /api/reports?profile=` 對齊（full / lite / crypto-only）；省略則不篩選。
 */
export function useReports(limit = 30, profile = null) {
  const qs = new URLSearchParams();
  qs.set("limit", String(limit));
  if (profile != null && String(profile).trim() !== "") {
    qs.set("profile", String(profile).trim());
  }
  const qstr = qs.toString();
  return useQuery({
    queryKey: ["reports", limit, profile ?? ""],
    queryFn: () => apiFetch(`/api/reports?${qstr}`),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

/** @param {{ enabled?: boolean }} [queryOptions] — merge with react-query options pattern (enabled only). */
export function useReport(date, queryOptions = {}) {
  const enabled =
    queryOptions.enabled !== undefined ? !!date && queryOptions.enabled : !!date;
  return useQuery({
    queryKey: ["report", date],
    queryFn: () => apiFetch(`/api/reports/${date}`),
    enabled,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}

/**
 * Phase 1：`GET /api/reports/profile-stats` — per-profile report counts for Archive 小圖。
 * @param {number} [days]
 */
export function useReportProfileStats(days = 30) {
  return useQuery({
    queryKey: ["reports", "profile-stats", days],
    queryFn: () => apiFetch(`/api/reports/profile-stats?days=${days}`),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

/** V2 block-based report envelope (`GET /api/reports/{date}/structured`). */
export function useStructuredReport(date, profile = "full", queryOptions = {}) {
  const q = encodeURIComponent(profile);
  const enabled =
    queryOptions.enabled !== undefined ? !!date && queryOptions.enabled : !!date;
  return useQuery({
    queryKey: ["report", "structured", date, profile],
    queryFn: () => apiFetch(`/api/reports/${date}/structured?profile=${q}`),
    enabled,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}

/** Inventory of ``config/brief_layouts/*.yaml`` (visualization_plan V3). */
export function useBriefLayouts(queryOptions = {}) {
  const enabled = queryOptions.enabled !== false;
  return useQuery({
    queryKey: ["brief-layouts"],
    queryFn: () => apiFetch("/api/brief-layouts"),
    enabled,
    staleTime: 60 * 60 * 1000,
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
      if (isServerErrorMessage(msg)) return failureCount < 2;
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
  const quoteSuffix = e2eSymbolQuery(normalized, "quote");
  return useQuery({
    queryKey: ["symbol", "quote", normalized, quoteSuffix || "default", livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/symbols/${encodeURIComponent(normalized)}/quote${quoteSuffix}`),
    enabled: !!normalized,
    staleTime: livePoll ? sharedStale : 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (isServerErrorMessage(msg)) return failureCount < 2;
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
  const snapSuffix = e2eSymbolQuery(normalized, "snapshot");
  const snapQs = `days=${days}&recommendation_limit=${recommendationLimit}${snapSuffix ? `&${snapSuffix.slice(1)}` : ""}`;
  return useQuery({
    queryKey: [
      "symbol",
      "snapshot",
      normalized,
      days,
      recommendationLimit,
      snapSuffix || "default",
      livePoll ? "live" : "static",
    ],
    queryFn: () => apiFetch(`/api/symbols/${encodeURIComponent(normalized)}/snapshot?${snapQs}`),
    enabled: !!normalized,
    staleTime: livePoll ? sharedStale : 3 * 60 * 1000,
    refetchInterval,
    retry: (failureCount, err) => {
      const msg = err instanceof Error ? err.message : String(err);
      if (isServerErrorMessage(msg)) return failureCount < 2;
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
      if (isServerErrorMessage(msg)) return failureCount < 2;
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
      qc.invalidateQueries({ queryKey: ["war-room"] });
      qc.invalidateQueries({ queryKey: ["metrics", "latest"] });
      qc.invalidateQueries({ queryKey: ["report"] });
      qc.invalidateQueries({ queryKey: ["positions", "open"] });
    },
  });
}
