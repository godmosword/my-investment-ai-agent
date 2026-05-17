import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useLocation } from "react-router-dom";
import { useSymbolFocus } from "../context/SymbolFocusContext";
import { useRunCrew, useRunCrewStatus } from "../hooks/useApi";
import { getTerminalCommandBarPlaceholder, getTerminalCommandExamples } from "../constants/portalPhase4";
import {
  TERMINAL_RECENT_SYMBOLS_KEY,
  TERMINAL_SSE_WATCH_CHANGED_EVENT,
  TERMINAL_SSE_WATCH_KEY,
} from "../constants/terminalStorage";

const RECENT_MAX = 8;
const BOARD_ROUTES = {
  NEWS: "/news",
  科技即時報: "/news",
  DASHBOARD: "/dashboard",
  數據儀表板: "/dashboard",
  MACRO: "/dashboard",
  MRKT: "/dashboard",
  INSIGHTS: "/insights",
  TERMINAL: "/insights",
  BRIEFS: "/insights",
  投資觀點: "/insights",
  COLUMNS: "/columns",
  科技專欄: "/columns",
  PORTFOLIO: "/portfolio",
  持倉: "/portfolio",
};

function readRecent() {
  try {
    const raw = String(globalThis.localStorage?.getItem(TERMINAL_RECENT_SYMBOLS_KEY) ?? "").trim();
    if (!raw) return [];
    return raw
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean)
      .slice(0, RECENT_MAX);
  } catch {
    return [];
  }
}

function pushRecent(sym) {
  const upper = String(sym ?? "").trim().toUpperCase();
  if (!upper) return readRecent();
  const next = [upper, ...readRecent().filter((s) => s !== upper)].slice(0, RECENT_MAX);
  try {
    globalThis.localStorage?.setItem(TERMINAL_RECENT_SYMBOLS_KEY, next.join(","));
  } catch {
    /* ignore */
  }
  return next;
}

function readWatchSet() {
  try {
    const raw = String(globalThis.localStorage?.getItem(TERMINAL_SSE_WATCH_KEY) ?? "").trim();
    if (!raw) return new Set();
    return new Set(
      raw
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
    );
  } catch {
    return new Set();
  }
}

function writeWatchSet(set) {
  const csv = [...set].filter(Boolean).slice(0, 16).join(",");
  try {
    if (csv) globalThis.localStorage?.setItem(TERMINAL_SSE_WATCH_KEY, csv);
    else globalThis.localStorage?.removeItem(TERMINAL_SSE_WATCH_KEY);
  } catch {
    /* ignore */
  }
  try {
    globalThis.dispatchEvent(new CustomEvent(TERMINAL_SSE_WATCH_CHANGED_EVENT));
  } catch {
    /* ignore */
  }
}

/** Return true when input is a RUN / ANALYZE trigger (e.g. "RUN", "AAPL ANALYZE") */
function isRunInput(raw) {
  const upper = String(raw ?? "").trim().toUpperCase();
  if (!upper) return false;
  const parts = upper.split(/\s+/).filter(Boolean);
  return parts[0] === "RUN" || parts[parts.length - 1] === "ANALYZE" || parts[parts.length - 1] === "RUN";
}

/** Parse `AAPL <GO>` / `aapl go` / `GO MSFT` → symbol */
function parseGoInput(raw) {
  const s = String(raw ?? "").trim();
  if (!s) return "";
  const upper = s.toUpperCase();
  const goIdx = upper.indexOf("<GO>");
  if (goIdx >= 0) return upper.slice(0, goIdx).trim().split(/\s+/).pop() ?? "";
  const parts = upper.split(/\s+/).filter(Boolean);
  if (parts.length >= 2 && parts[parts.length - 1] === "GO") {
    return parts[parts.length - 2] ?? "";
  }
  return parts[0] ?? "";
}

function parseBoardRoute(raw) {
  const upper = String(raw ?? "")
    .trim()
    .replace(/<GO>/gi, "")
    .replace(/\s+GO$/i, "")
    .trim()
    .toUpperCase();
  if (!upper) return "";
  if (upper.startsWith("/")) {
    const path = upper.toLowerCase();
    if (["/news", "/dashboard", "/insights", "/columns", "/portfolio"].includes(path)) return path;
  }
  return BOARD_ROUTES[upper] || "";
}

/**
 * Bloomberg-style command strip (GO, WATCH, recent chips).
 *
 * @param {object} props
 * @param {import("react").ReactNode | null} [props.trailing] — e.g. ``GlobalGateBadge``; rendered right of the focus label inside the bar.
 */
export default function TerminalCommandBar({ trailing = null }) {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { symbol, setSymbol } = useSymbolFocus();
  const inputRef = useRef(null);
  const lastCrewRunAtRef = useRef(0);
  const crewThrottleMs = 4500;
  const [input, setInput] = useState("");
  const [watchSet, setWatchSetState] = useState(() => readWatchSet());
  const [recent, setRecent] = useState(() => readRecent());
  const [runToast, setRunToast] = useState(null);
  const runCrew = useRunCrew();
  const crewStatus = useRunCrewStatus();

  useEffect(() => {
    if (!runCrew.isPending) return undefined;
    const id = setInterval(() => {
      qc.invalidateQueries({ queryKey: ["run-crew", "status"] });
    }, 800);
    return () => clearInterval(id);
  }, [runCrew.isPending, qc]);

  useEffect(() => {
    const bump = () => setWatchSetState(readWatchSet());
    globalThis.addEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
    globalThis.addEventListener("storage", bump);
    return () => {
      globalThis.removeEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
      globalThis.removeEventListener("storage", bump);
    };
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        const tag = String(e.target?.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return;
        e.preventDefault();
        try {
          inputRef.current?.focus();
        } catch {
          /* ignore */
        }
      }
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, []);

  const focused = (symbol || "").trim().toUpperCase();
  const inWatch = useMemo(() => focused && watchSet.has(focused), [focused, watchSet]);
  const crewHudActive = runCrew.isPending || crewStatus.data?.status === "running";
  const cmdPlaceholder = useMemo(
    () => getTerminalCommandBarPlaceholder(location.pathname),
    [location.pathname],
  );
  const commandExamples = useMemo(
    () => getTerminalCommandExamples(location.pathname),
    [location.pathname],
  );

  const showToast = useCallback((msg, isError = false) => {
    setRunToast({ msg, isError });
    const t = setTimeout(() => setRunToast(null), 4000);
    return () => clearTimeout(t);
  }, []);

  const onRun = useCallback(() => {
    if (runCrew.isPending) return;
    const now = Date.now();
    if (now - lastCrewRunAtRef.current < crewThrottleMs) {
      const waitS = Math.ceil((crewThrottleMs - (now - lastCrewRunAtRef.current)) / 1000);
      showToast(`請勿重複觸發 Crew（約 ${waitS}s 後可再試）`, true);
      return;
    }
    lastCrewRunAtRef.current = now;
    setInput("");
    runCrew.mutate(
      {},
      {
        onSuccess: (data) => {
          if (data?.ok) showToast(`Crew 已啟動 (job: ${data.job_id})`);
          else showToast(`Crew 執行中 (${data?.job_id ?? "?"})`, true);
        },
        onError: (err) => {
          const msg = err instanceof Error ? err.message : String(err);
          if (String(msg).startsWith("429:")) showToast("觸發過於頻繁（429），請稍後再試。", true);
          else showToast(`Crew 觸發失敗：${msg}`, true);
        },
      },
    );
  }, [runCrew, showToast, crewThrottleMs]);

  const onGo = useCallback(() => {
    if (isRunInput(input)) {
      onRun();
      return;
    }
    const route = parseBoardRoute(input);
    if (route) {
      navigate(route);
      setInput("");
      return;
    }
    const sym = parseGoInput(input);
    if (sym) {
      setSymbol(sym);
      setRecent(pushRecent(sym));
      navigate(`/insights?symbol=${encodeURIComponent(sym)}`);
    }
    setInput("");
  }, [input, setSymbol, onRun, navigate]);

  const onPickRecent = useCallback(
    (sym) => {
      if (!sym) return;
      setSymbol(sym);
      setRecent(pushRecent(sym));
      navigate(`/insights?symbol=${encodeURIComponent(sym)}`);
    },
    [setSymbol, navigate],
  );

  const toggleWatch = useCallback(() => {
    if (!focused) return;
    const next = readWatchSet();
    if (next.has(focused)) next.delete(focused);
    else next.add(focused);
    writeWatchSet(next);
    setWatchSetState(next);
  }, [focused]);

  return (
    <div
      data-testid="terminal-command-bar"
      className="flex flex-wrap items-center gap-1.5 border-b border-white/10 bg-black/30 px-2 py-1.5 md:gap-2 md:px-3"
      aria-label="Terminal Command Bar"
    >
      <span className="hidden text-[11px] uppercase tracking-wide text-[var(--muted)] sm:inline">Cmd</span>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onGo();
        }}
        placeholder={cmdPlaceholder}
        aria-label="Terminal command input"
        className="min-h-[40px] min-w-[150px] flex-1 rounded border border-white/15 bg-black/40 px-2 py-1 text-[13px] text-white placeholder:text-white/35 sm:min-h-[44px] sm:max-w-md"
        autoComplete="off"
        spellCheck={false}
        ref={inputRef}
      />
      <button
        type="button"
        className="min-h-[40px] rounded bg-emerald-700/80 px-3 py-1 text-[12px] font-semibold text-white hover:bg-emerald-600 sm:min-h-[44px]"
        onClick={onGo}
      >
        GO
      </button>
      <button
        type="button"
        data-testid="cmd-bar-run"
        disabled={runCrew.isPending}
        className="min-h-[40px] rounded border border-amber-500/40 bg-amber-600/20 px-3 py-1 text-[12px] font-semibold text-amber-300 hover:bg-amber-600/40 disabled:cursor-not-allowed disabled:opacity-40 sm:min-h-[44px]"
        onClick={onRun}
        title="觸發研究 Crew（需 CREW_HTTP_ENABLED=1）"
      >
        {runCrew.isPending ? "…" : "RUN"}
      </button>
      {runToast ? (
        <div
          data-testid="cmd-bar-run-toast"
          className={`ml-2 rounded px-2 py-1 text-[12px] ${runToast.isError ? "bg-red-900/60 text-red-300" : "bg-emerald-900/60 text-emerald-300"}`}
          role="status"
          aria-live="polite"
        >
          {runToast.msg}
        </div>
      ) : null}
      {crewHudActive ? (
        <div
          data-testid="terminal-crew-status-hud"
          className="w-full rounded border border-amber-500/25 bg-amber-950/35 px-2 py-1 text-[11px] leading-snug text-amber-100/90"
          role="status"
          aria-live="polite"
        >
          <span className="font-semibold text-amber-200/95">Crew</span>
          {runCrew.isPending ? " · 提交中…" : ` · ${String(crewStatus.data?.status || "—")}`}
          {crewStatus.data?.job_id ? (
            <span className="font-mono text-amber-100/85"> · {String(crewStatus.data.job_id)}</span>
          ) : null}
          {crewStatus.data?.started_at ? (
            <span className="text-amber-100/70"> · {String(crewStatus.data.started_at)}</span>
          ) : null}
          {crewStatus.data?.error ? (
            <span className="text-red-300/90"> · err {String(crewStatus.data.error)}</span>
          ) : null}
        </div>
      ) : null}
      <button
        type="button"
        disabled={!focused}
        className="min-h-[40px] rounded border border-white/20 bg-white/[0.03] px-3 py-1 text-[12px] text-white/90 hover:bg-white/5 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.02] disabled:text-white/30 sm:min-h-[44px]"
        onClick={toggleWatch}
        title="納入 SSE watch_symbols（最多 8 個由後端截斷）"
      >
        {inWatch ? "UNWATCH" : "WATCH"}
      </button>
      {focused ? (
        <span className="text-[12px] text-[var(--muted)]">
          關注：<span className="font-mono text-white/90">{focused}</span>
        </span>
      ) : null}
      {trailing ? <div className="order-last flex w-full items-center justify-end sm:order-none sm:ml-auto sm:w-auto">{trailing}</div> : null}
      {recent.length > 0 ? (
        <div
          data-testid="terminal-command-recent"
          className="flex w-full flex-wrap items-center gap-1 pt-1 text-[11px] text-[var(--muted)]"
        >
          <span className="uppercase tracking-wide">Recent</span>
          {recent.map((sym) => (
            <button
              key={sym}
              type="button"
              onClick={() => onPickRecent(sym)}
              className={`min-h-[32px] rounded border px-2 py-0.5 font-mono ${
                focused === sym
                  ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-200"
                  : "border-white/15 text-white/80 hover:bg-white/5"
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      ) : null}
      <details
        data-testid="terminal-command-help"
        className="w-full rounded border border-white/10 bg-white/[0.02] px-2 py-1 text-[11px] text-[var(--muted)]"
      >
        <summary className="cursor-pointer select-none text-white/75">指令範例與權限邊界</summary>
        <div className="mt-1 grid gap-1 sm:grid-cols-3">
          {commandExamples.map((item) => (
            <div key={`${item.label}:${item.command}`} className="rounded border border-white/10 bg-black/20 px-2 py-1">
              <span className="text-white/60">{item.label}</span>
              <code className="ml-1 rounded bg-black/35 px-1 font-mono text-emerald-200">{item.command}</code>
              <span className="block text-white/45">{item.note}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
