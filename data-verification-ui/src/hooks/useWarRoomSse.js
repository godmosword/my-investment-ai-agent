import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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

/** @typedef {{ id: string, ts: string, phase: string, node: string, summary: string, payload: object, severity: string }} GraphTelemetryLine */

const WarRoomGraphLogContext = createContext({
  /** @type {GraphTelemetryLine[]} */
  lines: [],
  clearGraphLog: () => {},
});

const MAX_GRAPH_LINES = 300;

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

function telemetrySeverity(d) {
  const phase = String(d?.phase ?? "end");
  if (phase === "begin") return "info";
  const node = String(d?.node ?? "");
  const p = d?.payload && typeof d.payload === "object" ? d.payload : d;
  if (node === "market_gate" && Number(p?.blocked) > 0) return "warn";
  if (node === "python_validate" && p?.passed === false) return "error";
  if (node === "llm_reviewer" && p?.passed === false) return "error";
  if (node === "trade_picker" && p?.reason && String(p.reason) !== "error") return "warn";
  if (node === "trade_picker" && p?.reason === "error") return "error";
  if (node === "final_formatter" && p?.degraded) return "warn";
  return "ok";
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
  const [graphLines, setGraphLines] = useState(() => /** @type {GraphTelemetryLine[]} */ ([]));

  const graphPendingRef = useRef([]);
  const graphRafRef = useRef(null);

  const flushGraphLines = useCallback(() => {
    graphRafRef.current = null;
    const batch = graphPendingRef.current;
    if (!batch.length) return;
    graphPendingRef.current = [];
    setGraphLines((prev) => {
      const next = [...prev, ...batch];
      return next.length > MAX_GRAPH_LINES ? next.slice(-MAX_GRAPH_LINES) : next;
    });
  }, []);

  const scheduleGraphAppend = useCallback(
    (entry) => {
      graphPendingRef.current.push(entry);
      if (graphRafRef.current != null) return;
      graphRafRef.current = globalThis.requestAnimationFrame(flushGraphLines);
    },
    [flushGraphLines],
  );

  const clearGraphLog = useCallback(() => {
    graphPendingRef.current = [];
    if (graphRafRef.current != null) {
      globalThis.cancelAnimationFrame(graphRafRef.current);
      graphRafRef.current = null;
    }
    setGraphLines([]);
  }, []);

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

    const onNodeComplete = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d?.phase === "begin" && d?.node === "trade_picker") {
          graphPendingRef.current = [];
          if (graphRafRef.current != null) {
            globalThis.cancelAnimationFrame(graphRafRef.current);
            graphRafRef.current = null;
          }
          setGraphLines([]);
        }
        const payload =
          d?.payload && typeof d.payload === "object" ? d.payload : { ...d };
        const line = {
          id:
            globalThis.crypto?.randomUUID?.() ??
            `${d?.ts ?? ""}-${d?.node ?? "?"}-${Math.random().toString(36).slice(2, 9)}`,
          ts: String(d?.ts ?? ""),
          phase: String(d?.phase ?? "end"),
          node: String(d?.node ?? "?"),
          summary: String(d?.summary ?? "").trim(),
          payload,
          severity: telemetrySeverity(d),
        };
        scheduleGraphAppend(line);
      } catch {
        /* ignore malformed */
      }
    };

    es.onmessage = scheduleRefresh;
    es.addEventListener("war_room_update", scheduleRefresh);
    es.addEventListener("symbol_quote", onSymbolQuote);
    es.addEventListener("node_complete", onNodeComplete);
    es.onerror = () => setSseStatus("error");

    return () => {
      if (refreshTimer != null) {
        globalThis.clearTimeout(refreshTimer);
      }
      if (graphRafRef.current != null) {
        globalThis.cancelAnimationFrame(graphRafRef.current);
        graphRafRef.current = null;
      }
      es.removeEventListener("symbol_quote", onSymbolQuote);
      es.removeEventListener("node_complete", onNodeComplete);
      es.close();
    };
  }, [qc, symbol, watchRev, scheduleGraphAppend]);

  const statusValue = useMemo(() => ({ sseStatus }), [sseStatus]);

  const graphValue = useMemo(
    () => ({ lines: graphLines, clearGraphLog }),
    [graphLines, clearGraphLog],
  );

  return createElement(
    WarRoomGraphLogContext.Provider,
    { value: graphValue },
    createElement(WarRoomSseStatusContext.Provider, { value: statusValue }, children),
  );
}

export function useWarRoomSseStatus() {
  return useContext(WarRoomSseStatusContext);
}

/** LangGraph ``node_complete`` telemetry lines (SSE); only populated when ``VITE_SSE_ENABLED=1``. */
export function useWarRoomGraphTelemetry() {
  return useContext(WarRoomGraphLogContext);
}
