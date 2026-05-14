import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { mergeSiliconHeaders } from "../lib/siliconApiHeaders";
import { siliconGetJson, siliconSendJson, siliconFetchRaw } from "../lib/siliconApiClient";

const E2E_MODE = import.meta.env.VITE_E2E === "1";

function handleApiUnauthorized() {
  if (E2E_MODE) return;
  try {
    globalThis.dispatchEvent(new CustomEvent("qsilicon:api-unauthorized"));
  } catch {
    /* ignore */
  }
  try {
    const path = globalThis.location?.pathname || "/insights";
    const q = globalThis.location?.search || "";
    const ret = encodeURIComponent(`${path}${q}`);
    globalThis.location?.assign(`/api-key?return=${ret}`);
  } catch {
    /* ignore */
  }
}

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

/** Insights Terminal workspace 輪詢間隔（ms）；可由 `VITE_TERMINAL_POLL_MS` 覆寫，預設 45s，最小 5s、最大 5min。 */
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

function terminalRetryPolicy(failureCount, err) {
  const msg = err instanceof Error ? err.message : String(err);
  if (isServerErrorMessage(msg)) return failureCount < 2;
  return failureCount < 1;
}

function terminalRetryDelay(attempt) {
  return Math.min(30_000, 1500 * 2 ** attempt);
}

function terminalLiveQueryOptions({
  livePoll,
  coalesceMultiplier,
  liveStaleTime,
  staticStaleTime,
}) {
  const interval = livePoll ? getTerminalRefetchIntervalMs() : false;
  const coalesce = getTerminalQueryCoalesce();
  return {
    staleTime: livePoll ? liveStaleTime(interval || getTerminalRefetchIntervalMs()) : staticStaleTime,
    refetchInterval: coalesce && livePoll ? interval * coalesceMultiplier : interval,
    retry: terminalRetryPolicy,
    retryDelay: terminalRetryDelay,
  };
}

function mergeExecutionIntentRow(existing, next) {
  if (!existing) return next;
  return { ...existing, ...next };
}

function updateExecutionIntentRows(oldRows, nextRow) {
  if (!Array.isArray(oldRows)) return oldRows;
  let found = false;
  const updated = oldRows.map((row) => {
    if (row?.signal_id !== nextRow?.signal_id) return row;
    found = true;
    return mergeExecutionIntentRow(row, nextRow);
  });
  return found ? updated : oldRows;
}

function updateWarRoomPayload(oldPayload, nextRow) {
  if (!oldPayload || typeof oldPayload !== "object") return oldPayload;
  if (!Array.isArray(oldPayload.execution_intents)) return oldPayload;
  return {
    ...oldPayload,
    execution_intents: updateExecutionIntentRows(oldPayload.execution_intents, nextRow),
  };
}

/**
 * Terminal / Today query sync policy:
 * - `execution-intents` + `war-room` are user-visible and may refetch immediately when active.
 * - `metrics/latest` + `report` + `positions/open` are marked stale only, then picked up by the
 *   next poll / navigation / manual refresh to avoid bursty full-page refetches.
 */
export function syncWarRoomRelatedQueries(
  queryClient,
  {
    executionIntentsRefetchType = "active",
    warRoomRefetchType = "active",
    metricsRefetchType = "none",
    reportRefetchType = "none",
    positionsRefetchType = "none",
    positionsListRefetchType = "none",
  } = {},
) {
  queryClient.invalidateQueries({
    queryKey: ["execution-intents"],
    refetchType: executionIntentsRefetchType,
  });
  queryClient.invalidateQueries({
    queryKey: ["war-room"],
    refetchType: warRoomRefetchType,
  });
  queryClient.invalidateQueries({
    queryKey: ["metrics", "latest"],
    refetchType: metricsRefetchType,
  });
  queryClient.invalidateQueries({
    queryKey: ["report"],
    refetchType: reportRefetchType,
  });
  queryClient.invalidateQueries({
    queryKey: ["positions", "open"],
    refetchType: positionsRefetchType,
  });
  queryClient.invalidateQueries({
    queryKey: ["positions", "list"],
    refetchType: positionsListRefetchType,
  });
}

async function apiFetch(path) {
  return siliconGetJson(path, handleApiUnauthorized);
}

/** GET /api/scenario/suggestions — 404（功能關閉）回 `{ disabled: true }`，其餘錯誤仍拋出。 */
async function apiFetchScenarioSuggestions() {
  let res;
  try {
    res = await siliconFetchRaw("/api/scenario/suggestions", { method: "GET" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (res.status === 404) {
    return { disabled: true };
  }
  if (!res.ok) {
    if (res.status === 401) handleApiUnauthorized();
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
  return siliconSendJson(path, "PATCH", body, {}, handleApiUnauthorized);
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

export function useMacroSnapshot() {
  return useQuery({
    queryKey: ["macro", "snapshot"],
    queryFn: () => apiFetch("/api/macro/snapshot"),
    staleTime: 60 * 1000,
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

/** Reviewer loop gate status for one date (`GET /api/reports/{date}/gate-status`). */
export function useGateStatus(date) {
  return useQuery({
    queryKey: ["gate-status", date],
    queryFn: () => apiFetch(`/api/reports/${date}/gate-status`),
    enabled: !!date,
    staleTime: 15 * 60 * 1000,
    retry: false,
  });
}

/** QSREC reviewer_log aggregate stats for the last N days. */
export function useQsrecStats(days = 7) {
  return useQuery({
    queryKey: ["qsrec-stats", days],
    queryFn: () => apiFetch(`/api/reports/qsrec-stats?days=${days}`),
    staleTime: 15 * 60 * 1000,
    retry: false,
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

/**
 * Fetch multiple structured reports in parallel (safe for dynamic date arrays).
 * Returns array of { data, isLoading, error } in the same order as dates.
 */
export function useStructuredReports(dates, profile = "full") {
  const q = encodeURIComponent(profile);
  return useQueries({
    queries: (dates ?? []).map((date) => ({
      queryKey: ["report", "structured", date, profile],
      queryFn: () => apiFetch(`/api/reports/${date}/structured?profile=${q}`),
      enabled: !!date,
      staleTime: 30 * 60 * 1000,
      retry: 1,
    })),
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

/** M4 aggregate list (defaults server-side to OPEN). */
export function usePositionsList(days = 90, status = "OPEN") {
  const st = (status || "OPEN").trim().toUpperCase();
  return useQuery({
    queryKey: ["positions", "list", days, st],
    queryFn: () => {
      const p = new URLSearchParams({ days: String(days) });
      if (st) p.set("status", st);
      return apiFetch(`/api/positions?${p}`);
    },
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useIndustryThemes(limit = 80) {
  return useQuery({
    queryKey: ["industries", "themes", limit],
    queryFn: () => apiFetch(`/api/industries/themes?limit=${limit}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useNewsDigest({ date, limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (date) params.set("date", date);
  return useQuery({
    queryKey: ["news", "digest", date ?? "", limit],
    queryFn: () => apiFetch(`/api/news/digest?${params}`),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useNewsDeep(itemId) {
  const id = String(itemId ?? "").trim();
  return useQuery({
    queryKey: ["news", "deep", id],
    queryFn: () => apiFetch(`/api/news/deep/${encodeURIComponent(id)}`),
    enabled: Boolean(id),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useNewsDeepList({ pillar, limit = 20 } = {}) {
  const normalized = String(pillar ?? "").trim().toLowerCase();
  const params = new URLSearchParams({ limit: String(limit) });
  if (normalized) params.set("pillar", normalized);
  return useQuery({
    queryKey: ["news", "deep-list", normalized, limit],
    queryFn: () => apiFetch(`/api/news/deep?${params}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useNewsThemes(limit = 80) {
  return useQuery({
    queryKey: ["news", "themes", limit],
    queryFn: () => apiFetch(`/api/news/themes?limit=${limit}`),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useAnalysisBundle(symbol, days = 30, recommendationLimit = 12) {
  const sym = (symbol ?? "").trim().toUpperCase();
  const qs = new URLSearchParams({
    days: String(days),
    recommendation_limit: String(recommendationLimit),
  });
  return useQuery({
    queryKey: ["analysis", "bundle", sym, days, recommendationLimit],
    queryFn: () => apiFetch(`/api/analysis/${encodeURIComponent(sym)}?${qs}`),
    enabled: !!sym,
    staleTime: 3 * 60 * 1000,
    retry: 1,
  });
}

export function useQuantSignals() {
  return useQuery({
    queryKey: ["quant", "signals"],
    queryFn: () => apiFetch("/api/quant/signals"),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export function useQuantBacktest(symbol) {
  const sym = String(symbol ?? "").trim().toUpperCase();
  return useQuery({
    queryKey: ["quant", "backtest", sym],
    queryFn: () => apiFetch(`/api/quant/backtest?symbol=${encodeURIComponent(sym)}`),
    enabled: Boolean(sym),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}

export function useTrackRecordSummary() {
  return useQuery({
    queryKey: ["track-record", "summary"],
    queryFn: () => apiFetch("/api/track-record/summary"),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useTrackRecordClosed(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["track-record", "closed", limit, offset],
    queryFn: () => apiFetch(`/api/track-record/closed?limit=${limit}&offset=${offset}`),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useTrackRecordByTag(tag, limit = 50, offset = 0) {
  const normalized = String(tag ?? "").trim().toUpperCase();
  return useQuery({
    queryKey: ["track-record", "by-tag", normalized, limit, offset],
    queryFn: () =>
      apiFetch(
        `/api/track-record/by-tag?tag=${encodeURIComponent(normalized)}&limit=${limit}&offset=${offset}`,
      ),
    enabled: Boolean(normalized),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useWarRoomLatest(options = {}) {
  const livePoll = Boolean(options.livePoll);
  return useQuery({
    queryKey: ["war-room", "latest", livePoll ? "live" : "static"],
    queryFn: () => apiFetch("/api/war-room/latest"),
    ...terminalLiveQueryOptions({
      livePoll,
      coalesceMultiplier: 1.05,
      liveStaleTime: (interval) => Math.min(interval, 60_000),
      staticStaleTime: 60 * 1000,
    }),
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
  const normalized = (symbol ?? "").trim().toUpperCase();
  const quoteSuffix = e2eSymbolQuery(normalized, "quote");
  return useQuery({
    queryKey: ["symbol", "quote", normalized, quoteSuffix || "default", livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/symbols/${encodeURIComponent(normalized)}/quote${quoteSuffix}`),
    enabled: !!normalized,
    ...terminalLiveQueryOptions({
      livePoll,
      coalesceMultiplier: 1.1,
      liveStaleTime: () => getTerminalSharedStaleTimeMs(),
      staticStaleTime: 60 * 1000,
    }),
  });
}

export function useSymbolSnapshot(symbol, days = 30, recommendationLimit = 12, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const normalized = (symbol ?? "").trim().toUpperCase();
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
    ...terminalLiveQueryOptions({
      livePoll,
      coalesceMultiplier: 1.15,
      liveStaleTime: () => getTerminalSharedStaleTimeMs(),
      staticStaleTime: 3 * 60 * 1000,
    }),
  });
}

export function useExecutionIntents(limit = 50, options = {}) {
  const livePoll = Boolean(options.livePoll);
  const status = options.statusFilter && options.statusFilter !== "all" ? String(options.statusFilter) : "";
  const category = options.categoryFilter && options.categoryFilter !== "all" ? String(options.categoryFilter) : "";
  const sortBy = options.sortBy || "updated_desc";
  const params = new URLSearchParams({ limit: String(limit), sort_by: sortBy });
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  return useQuery({
    queryKey: ["execution-intents", limit, sortBy, status || "all", category || "all", livePoll ? "live" : "static"],
    queryFn: () => apiFetch(`/api/execution-intents?${params}`),
    ...terminalLiveQueryOptions({
      livePoll,
      coalesceMultiplier: 1.08,
      liveStaleTime: (interval) => Math.min(interval, 60_000),
      staticStaleTime: 2 * 60 * 1000,
    }),
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

export function usePaperLifecycle({ limit = 200, status = "", category = "" } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  return useQuery({
    queryKey: ["paper", "lifecycle", limit, status || "all", category || "all"],
    queryFn: () => apiFetch(`/api/paper/lifecycle?${params}`),
    staleTime: 45 * 1000,
    retry: 1,
  });
}

export function usePaperPnl({ limit = 200, status = "", category = "" } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  return useQuery({
    queryKey: ["paper", "pnl", limit, status || "all", category || "all"],
    queryFn: () => apiFetch(`/api/paper/pnl?${params}`),
    staleTime: 45 * 1000,
    retry: 1,
  });
}

export function usePaperTransparencyLetter(month = "") {
  const normalized = String(month ?? "").trim();
  const params = new URLSearchParams();
  if (normalized) params.set("month", normalized);
  return useQuery({
    queryKey: ["paper", "transparency-letter", normalized || "current"],
    queryFn: () => apiFetch(`/api/paper/transparency-letter${params.toString() ? `?${params}` : ""}`),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}

export function useScenarioSuggestions() {
  return useQuery({
    queryKey: ["scenario", "suggestions"],
    queryFn: () => apiFetchScenarioSuggestions(),
    staleTime: 60 * 1000,
    retry: false,
  });
}

async function apiPostJson(path, body = {}, extraHeaders = {}) {
  return siliconSendJson(path, "POST", body, extraHeaders, handleApiUnauthorized);
}

async function apiPostForm(path, formData) {
  let res;
  try {
    res = await siliconFetchRaw(path, {
      method: "POST",
      body: formData,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(`Network error (${msg})`);
  }
  if (!res.ok) {
    if (res.status === 401) handleApiUnauthorized();
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

async function apiDelete(path) {
  return siliconSendJson(path, "DELETE", undefined, {}, handleApiUnauthorized);
}

export function usePortfolioHoldings() {
  return useQuery({
    queryKey: ["portfolio", "holdings"],
    queryFn: () => apiFetch("/api/portfolio"),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function usePortfolioPnl() {
  return useQuery({
    queryKey: ["portfolio", "pnl"],
    queryFn: () => apiFetch("/api/portfolio/pnl"),
    staleTime: 45 * 1000,
    retry: 1,
  });
}

export function useAddHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => apiPostJson("/api/portfolio", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useUpdateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }) => apiPatchJson(`/api/portfolio/${encodeURIComponent(id)}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => apiDelete(`/api/portfolio/${encodeURIComponent(id)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useImportCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (csvText) => {
      const form = new FormData();
      form.append("file", new Blob([csvText], { type: "text/csv" }), "holdings.csv");
      return apiPostForm("/api/portfolio/import", form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function usePriceAlerts() {
  return useQuery({
    queryKey: ["price-alerts"],
    queryFn: () => apiFetch("/api/push/price-alerts"),
    staleTime: 60 * 1000,
    retry: 1,
  });
}

/** Read-only aggregate for workspace digest (no quote fetches). */
export function usePriceAlertDigest() {
  return useQuery({
    queryKey: ["price-alerts", "digest"],
    queryFn: () => apiFetch("/api/push/price-alerts/digest"),
    staleTime: 45 * 1000,
    retry: 1,
  });
}

export function useCreatePriceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => apiPostJson("/api/push/price-alerts", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price-alerts"] });
      qc.invalidateQueries({ queryKey: ["price-alerts", "digest"] });
    },
  });
}

export function useDeletePriceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => apiDelete(`/api/push/price-alerts/${encodeURIComponent(id)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price-alerts"] });
      qc.invalidateQueries({ queryKey: ["price-alerts", "digest"] });
    },
  });
}

export function useCheckPriceAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sendPush = false } = {}) =>
      apiPostJson(`/api/push/price-alerts/check?send_push=${sendPush ? "true" : "false"}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price-alerts"] });
      qc.invalidateQueries({ queryKey: ["price-alerts", "digest"] });
    },
  });
}

export function useRunCrewStatus() {
  return useQuery({
    queryKey: ["run-crew", "status"],
    queryFn: () => apiFetch("/api/run-crew/status"),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" ? 2_000 : false;
    },
  });
}

export function useRunCrew() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ apiKey } = {}) =>
      apiPostJson("/api/run-crew", {}, apiKey ? { "X-Crew-Api-Key": apiKey } : {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run-crew", "status"] });
    },
  });
}

export function useCreateExecutionIntent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => apiPostJson("/api/execution-intents", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution-intents"] });
      qc.invalidateQueries({ queryKey: ["paper"] });
      qc.invalidateQueries({ queryKey: ["war-room"] });
    },
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
    onSuccess: (updatedRow) => {
      qc.setQueriesData({ queryKey: ["execution-intents"] }, (old) =>
        updateExecutionIntentRows(old, updatedRow),
      );
      qc.setQueriesData({ queryKey: ["war-room"] }, (old) =>
        updateWarRoomPayload(old, updatedRow),
      );
      syncWarRoomRelatedQueries(qc);
      qc.invalidateQueries({ queryKey: ["paper"] });
    },
  });
}
