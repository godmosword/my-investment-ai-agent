import { useCallback, useEffect, useMemo, useState } from "react";
import { useSymbolFocus } from "../context/SymbolFocusContext";
import { useRunCrew } from "../hooks/useApi";
import {
  TERMINAL_RECENT_SYMBOLS_KEY,
  TERMINAL_SSE_WATCH_CHANGED_EVENT,
  TERMINAL_SSE_WATCH_KEY,
} from "../constants/terminalStorage";

const RECENT_MAX = 8;

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

/**
 * Bloomberg-style command strip (GO, WATCH, recent chips).
 *
 * @param {object} props
 * @param {import("react").ReactNode | null} [props.trailing] — e.g. ``GlobalGateBadge``; rendered right of the focus label inside the bar.
 */
export default function TerminalCommandBar({ trailing = null }) {
  const { symbol, setSymbol } = useSymbolFocus();
  const [input, setInput] = useState("");
  const [watchSet, setWatchSetState] = useState(() => readWatchSet());
  const [recent, setRecent] = useState(() => readRecent());
  const [runToast, setRunToast] = useState(null);
  const runCrew = useRunCrew();

  useEffect(() => {
    const bump = () => setWatchSetState(readWatchSet());
    globalThis.addEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
    globalThis.addEventListener("storage", bump);
    return () => {
      globalThis.removeEventListener(TERMINAL_SSE_WATCH_CHANGED_EVENT, bump);
      globalThis.removeEventListener("storage", bump);
    };
  }, []);

  const focused = (symbol || "").trim().toUpperCase();
  const inWatch = useMemo(() => focused && watchSet.has(focused), [focused, watchSet]);

  const showToast = useCallback((msg, isError = false) => {
    setRunToast({ msg, isError });
    const t = setTimeout(() => setRunToast(null), 4000);
    return () => clearTimeout(t);
  }, []);

  const onRun = useCallback(() => {
    setInput("");
    runCrew.mutate(
      {},
      {
        onSuccess: (data) => {
          if (data?.ok) showToast(`Crew 已啟動 (job: ${data.job_id})`);
          else showToast(`Crew 執行中 (${data?.job_id ?? "?"})`, true);
        },
        onError: (err) => showToast(`Crew 觸發失敗：${err.message}`, true),
      },
    );
  }, [runCrew, showToast]);

  const onGo = useCallback(() => {
    if (isRunInput(input)) {
      onRun();
      return;
    }
    const sym = parseGoInput(input);
    if (sym) {
      setSymbol(sym);
      setRecent(pushRecent(sym));
    }
    setInput("");
  }, [input, setSymbol, onRun]);

  const onPickRecent = useCallback(
    (sym) => {
      if (!sym) return;
      setSymbol(sym);
      setRecent(pushRecent(sym));
    },
    [setSymbol],
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
      className="flex flex-wrap items-center gap-2 border-b border-white/10 bg-black/30 px-2 py-1.5 md:px-3"
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
        placeholder="AAPL &lt;GO&gt; | RUN"
        className="min-w-[140px] flex-1 rounded border border-white/15 bg-black/40 px-2 py-1 text-[13px] text-white placeholder:text-white/35 sm:max-w-md"
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="button"
        className="rounded bg-emerald-700/80 px-2 py-1 text-[12px] font-semibold text-white hover:bg-emerald-600"
        onClick={onGo}
      >
        GO
      </button>
      <button
        type="button"
        data-testid="cmd-bar-run"
        disabled={runCrew.isPending}
        className="rounded border border-amber-500/40 bg-amber-600/20 px-2 py-1 text-[12px] font-semibold text-amber-300 hover:bg-amber-600/40 disabled:cursor-not-allowed disabled:opacity-40"
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
      <button
        type="button"
        disabled={!focused}
        className="rounded border border-white/20 px-2 py-1 text-[12px] text-white/90 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
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
      {trailing ? <div className="ml-auto flex items-center">{trailing}</div> : null}
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
              className={`rounded border px-1.5 py-0.5 font-mono ${
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
    </div>
  );
}
