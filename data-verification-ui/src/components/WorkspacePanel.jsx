import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useIndustryThemes,
  usePaperLifecycle,
  usePortfolioPnl,
  usePriceAlerts,
  usePriceAlertDigest,
} from "../hooks/useApi";
import { emitWorkspaceChanged, QSI_WORKSPACE_CHANGED_EVENT } from "../constants/workspaceSync";

const WORKSPACE_KEYS = [
  "qsi_watchlist",
  "terminal_recent_symbols",
  "terminal_sse_watch",
  "qs_workspace_layout",
  "qs_workspace_panels",
  "qs_workspace_size_weights_v1",
];
const EVENT_KEYS = {
  qsi_watchlist: "qsi_watchlist_changed",
};
const DEFAULT_PANELS = ["paper", "portfolio", "columns", "alerts"];
const PANEL_LABELS = {
  paper: "Paper",
  portfolio: "Portfolio",
  columns: "Columns",
  alerts: "Alerts",
};

function readWorkspace() {
  const payload = {
    version: 1,
    exported_at: new Date().toISOString(),
    keys: {},
  };
  for (const key of WORKSPACE_KEYS) {
    try {
      payload.keys[key] = globalThis.localStorage?.getItem(key) ?? "";
    } catch {
      payload.keys[key] = "";
    }
  }
  return payload;
}

function writeWorkspace(payload) {
  const keys = payload?.keys && typeof payload.keys === "object" ? payload.keys : {};
  for (const key of WORKSPACE_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(keys, key)) continue;
    const value = keys[key];
    try {
      if (value == null || value === "") globalThis.localStorage?.removeItem(key);
      else globalThis.localStorage?.setItem(key, String(value));
    } catch {
      /* ignore */
    }
    if (EVENT_KEYS[key]) {
      try {
        globalThis.dispatchEvent(new CustomEvent(EVENT_KEYS[key]));
      } catch {
        /* ignore */
      }
    }
  }
}

function readPanels() {
  try {
    const parsed = JSON.parse(globalThis.localStorage?.getItem("qs_workspace_panels") || "[]");
    const values = Array.isArray(parsed) ? parsed.filter((key) => PANEL_LABELS[key]) : [];
    return values.length ? values : DEFAULT_PANELS;
  } catch {
    return DEFAULT_PANELS;
  }
}

function savePanels(panels) {
  try {
    globalThis.localStorage?.setItem("qs_workspace_panels", JSON.stringify(panels));
  } catch {
    /* ignore */
  }
  emitWorkspaceChanged();
}

const SIZE_STORE_KEY = "qs_workspace_size_weights_v1";

function readSizeStoreObj() {
  try {
    const raw = globalThis.localStorage?.getItem(SIZE_STORE_KEY);
    if (!raw) return { sm: {}, md: {} };
    const o = JSON.parse(raw);
    if (!o || typeof o !== "object") return { sm: {}, md: {} };
    return {
      sm: typeof o.sm === "object" && o.sm ? o.sm : {},
      md: typeof o.md === "object" && o.md ? o.md : {},
    };
  } catch {
    return { sm: {}, md: {} };
  }
}

function writeSizeStoreObj(obj) {
  try {
    globalThis.localStorage?.setItem(SIZE_STORE_KEY, JSON.stringify(obj));
  } catch {
    /* ignore */
  }
  emitWorkspaceChanged();
}

function equalSplitWeights(panelKeys) {
  const keys = panelKeys.filter((k) => PANEL_LABELS[k]);
  const n = keys.length || 1;
  const base = Math.floor(100 / n);
  let rem = 100 - base * n;
  const out = {};
  for (const k of keys) {
    out[k] = base + (rem > 0 ? 1 : 0);
    if (rem > 0) rem -= 1;
  }
  return out;
}

/** Saved per-breakpoint panel height % for preview stack; sum 100, min 5 each when n>1. */
function weightsForPanels(panelKeys, savedBp) {
  const keys = panelKeys.filter((k) => PANEL_LABELS[k]);
  if (!keys.length) return {};
  if (keys.length === 1) return { [keys[0]]: 100 };
  const d = equalSplitWeights(keys);
  for (const k of keys) {
    const v = Number(savedBp[k]);
    if (Number.isFinite(v) && v >= 5 && v <= 95) d[k] = Math.round(v);
  }
  let sum = keys.reduce((s, k) => s + (d[k] || 0), 0);
  let diff = 100 - sum;
  const last = keys[keys.length - 1];
  d[last] = (d[last] || 0) + diff;
  if (d[last] < 5) {
    const bump = 5 - d[last];
    d[last] = 5;
    const first = keys[0];
    d[first] = Math.max(5, (d[first] || 0) - bump);
    sum = keys.reduce((s, k) => s + (d[k] || 0), 0);
    diff = 100 - sum;
    d[last] = (d[last] || 0) + diff;
  }
  return d;
}

function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function WorkspacePanel({ compact = false } = {}) {
  const [layout, setLayout] = useState("balanced");
  const [panels, setPanels] = useState(DEFAULT_PANELS);
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState("");
  const portfolio = usePortfolioPnl();
  const paper = usePaperLifecycle();
  const themes = useIndustryThemes(8);
  const alerts = usePriceAlerts();
  const alertDigest = usePriceAlertDigest();

  const [bpLabel, setBpLabel] = useState("sm");
  const [weights, setWeights] = useState({});
  const weightsRef = useRef({});
  const dragRef = useRef(null);

  useEffect(() => {
    weightsRef.current = weights;
  }, [weights]);

  useEffect(() => {
    const mq = globalThis.matchMedia?.("(min-width:768px)");
    if (!mq) return undefined;
    const sync = () => setBpLabel(mq.matches ? "md" : "sm");
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const store = readSizeStoreObj();
    const saved = store[bpLabel] || {};
    setWeights(weightsForPanels(panels, saved));
  }, [panels, bpLabel]);

  const startDividerDrag = useCallback(
    (index) => (e) => {
      e.preventDefault();
      const top = panels[index];
      const bot = panels[index + 1];
      if (!top || !bot) return;
      const wTop = weightsRef.current[top] ?? Math.floor(100 / panels.length);
      const wBot = weightsRef.current[bot] ?? Math.floor(100 / panels.length);
      dragRef.current = { top, bot, startY: e.clientY, wTop, wBot };
      const onMove = (ev) => {
        const d = dragRef.current;
        if (!d) return;
        const dy = ev.clientY - d.startY;
        const delta = Math.round(dy / 5);
        let nTop = d.wTop - delta;
        let nBot = d.wBot + delta;
        const MIN = 5;
        if (nTop < MIN) {
          nBot -= MIN - nTop;
          nTop = MIN;
        }
        if (nBot < MIN) {
          nTop -= MIN - nBot;
          nBot = MIN;
        }
        setWeights((prev) => ({ ...prev, [d.top]: nTop, [d.bot]: nBot }));
      };
      const onUp = () => {
        dragRef.current = null;
        globalThis.removeEventListener("pointermove", onMove);
        globalThis.removeEventListener("pointerup", onUp);
        const store = readSizeStoreObj();
        store[bpLabel] = { ...weightsRef.current };
        writeSizeStoreObj(store);
        setMessage(`Panel heights saved (${bpLabel})`);
      };
      globalThis.addEventListener("pointermove", onMove);
      globalThis.addEventListener("pointerup", onUp, { once: true });
    },
    [panels, bpLabel],
  );

  useEffect(() => {
    try {
      setLayout(globalThis.localStorage?.getItem("qs_workspace_layout") || "balanced");
    } catch {
      setLayout("balanced");
    }
    setPanels(readPanels());
  }, []);

  const applyWorkspaceFromStorage = useCallback(() => {
    try {
      setLayout(globalThis.localStorage?.getItem("qs_workspace_layout") || "balanced");
    } catch {
      setLayout("balanced");
    }
    const nextPanels = readPanels();
    setPanels(nextPanels);
    const store = readSizeStoreObj();
    const saved = store[bpLabel] || {};
    setWeights(weightsForPanels(nextPanels, saved));
  }, [bpLabel]);

  useEffect(() => {
    const onStorage = (e) => {
      if (!e.key || !WORKSPACE_KEYS.includes(e.key)) return;
      applyWorkspaceFromStorage();
    };
    const onLocal = () => applyWorkspaceFromStorage();
    globalThis.addEventListener("storage", onStorage);
    globalThis.addEventListener(QSI_WORKSPACE_CHANGED_EVENT, onLocal);
    return () => {
      globalThis.removeEventListener("storage", onStorage);
      globalThis.removeEventListener(QSI_WORKSPACE_CHANGED_EVENT, onLocal);
    };
  }, [applyWorkspaceFromStorage]);

  const digest = useMemo(() => {
    const alertRows = alerts.data?.alerts ?? [];
    const d = alertDigest.data;
    const themeRows = themes.data?.themes ?? [];
    return {
      portfolioValue: portfolio.data?.total_value,
      portfolioPnl: portfolio.data?.total_pnl,
      paperActive: paper.data?.summary?.active_count ?? 0,
      paperClosed: paper.data?.summary?.closed_count ?? 0,
      topTheme: themeRows[0]?.label || "—",
      alertsTotal: d?.total ?? alertRows.length,
      alertsTriggered: d?.triggered ?? alertRows.filter((item) => item.triggered_at).length,
      alertsPending: d?.pending,
      alertSymbolsFull: Array.isArray(d?.symbols) ? d.symbols.join(", ") : "",
      alertSymbolsShort: Array.isArray(d?.symbols) ? d.symbols.slice(0, 6).join(", ") : "",
      alertSymbolsMore: Array.isArray(d?.symbols) && d.symbols.length > 6,
      alertDigestAsOf: d?.as_of ?? "",
    };
  }, [alerts.data, alertDigest.data, paper.data, portfolio.data, themes.data]);

  const updateLayout = (value) => {
    setLayout(value);
    try {
      globalThis.localStorage?.setItem("qs_workspace_layout", value);
    } catch {
      /* ignore */
    }
    emitWorkspaceChanged();
    setMessage("Workspace layout saved");
  };

  const updatePanels = (next) => {
    const clean = next.filter((key, index) => PANEL_LABELS[key] && next.indexOf(key) === index);
    const saved = clean.length ? clean : DEFAULT_PANELS;
    setPanels(saved);
    savePanels(saved);
    setMessage("Workspace panels saved");
  };

  const togglePanel = (key) => {
    if (panels.includes(key)) updatePanels(panels.filter((item) => item !== key));
    else updatePanels([...panels, key]);
  };

  const movePanel = (key, delta) => {
    const index = panels.indexOf(key);
    const nextIndex = index + delta;
    if (index < 0 || nextIndex < 0 || nextIndex >= panels.length) return;
    const next = [...panels];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    updatePanels(next);
  };

  const exportWorkspace = () => {
    const blob = new Blob([JSON.stringify(readWorkspace(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "qsi-workspace.json";
    a.click();
    URL.revokeObjectURL(url);
    setMessage("Workspace exported");
  };

  const importWorkspace = () => {
    try {
      const parsed = JSON.parse(importText);
      writeWorkspace(parsed);
      emitWorkspaceChanged();
      setLayout(globalThis.localStorage?.getItem("qs_workspace_layout") || "balanced");
      setPanels(readPanels());
      setImportText("");
      setMessage("Workspace imported");
    } catch (err) {
      setMessage(`Import failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <section className="card p-3" data-testid="workspace-panel">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="card-title">Workspace</div>
          <div className="text-[12px] text-[var(--muted)]">local layout · panel order · cross-board digest</div>
          <div className="text-[10px] text-white/45" data-testid="workspace-cross-tab-sync-hint">
            跨分頁／多視窗：另開同源分頁修改此區會經 localStorage 自動同步（Phase 2）。
          </div>
        </div>
        <button
          type="button"
          data-testid="workspace-export"
          className="min-h-[40px] rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/80 hover:bg-white/5"
          onClick={exportWorkspace}
        >
          Export
        </button>
      </div>

      <label className="block text-[12px] text-white/70">
        Layout
        <select
          data-testid="workspace-layout"
          value={layout}
          onChange={(e) => updateLayout(e.target.value)}
          className="mt-1 min-h-[40px] w-full rounded border border-white/15 bg-black/25 px-2 text-[13px] text-white"
        >
          <option value="balanced">balanced</option>
          <option value="dense">dense</option>
          <option value="focus">focus</option>
        </select>
      </label>

      <div className="mt-3 rounded border border-white/10 bg-white/[0.03] p-2" data-testid="workspace-digest">
        <div className="mb-2 text-[11px] font-semibold uppercase text-cyan-200">Digest</div>
        <div className="grid grid-cols-2 gap-2 text-[12px]">
          <div>
            <div className="text-[var(--muted)]">Portfolio</div>
            <div className="font-mono text-white">{money(digest.portfolioValue)}</div>
            <div className={Number(digest.portfolioPnl) >= 0 ? "text-emerald-300" : "text-red-300"}>
              {money(digest.portfolioPnl)}
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)]">Paper</div>
            <div className="text-white">{digest.paperActive} active</div>
            <div className="text-white/60">{digest.paperClosed} closed</div>
          </div>
          <div>
            <div className="text-[var(--muted)]">Columns</div>
            <div className="truncate text-white">{digest.topTheme}</div>
          </div>
          <div>
            <div className="text-[var(--muted)]">Alerts</div>
            <div className="text-white">{digest.alertsTotal} total</div>
            <div className="text-amber-200">{digest.alertsTriggered} triggered</div>
            {digest.alertsPending != null ? (
              <div className="text-white/60">{digest.alertsPending} pending</div>
            ) : null}
            {digest.alertSymbolsShort ? (
              <div className="truncate text-[11px] text-white/50" title={digest.alertSymbolsFull}>
                {digest.alertSymbolsShort}
                {digest.alertSymbolsMore ? "…" : ""}
              </div>
            ) : null}
            {digest.alertDigestAsOf ? (
              <div className="text-[10px] text-white/40" data-testid="workspace-alert-digest-asof">
                digest as_of {new Date(digest.alertDigestAsOf).toLocaleString("zh-TW", { hour12: false })}
              </div>
            ) : alertDigest.isError ? (
              <div className="text-[10px] text-amber-100/80">digest API 不可用</div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mt-3 rounded border border-white/10 bg-white/[0.03] p-2" data-testid="workspace-window-grid">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="text-[11px] font-semibold uppercase text-cyan-200">Windows</div>
          <div className="text-[11px] text-[var(--muted)]">{panels.length} active</div>
        </div>
        <div className="space-y-2">
          {Object.keys(PANEL_LABELS).map((key) => (
            <div key={key} className="flex items-center justify-between gap-2 rounded border border-white/10 px-2 py-1.5 text-[12px]">
              <label className="flex min-w-0 items-center gap-2 text-white/75">
                <input
                  type="checkbox"
                  checked={panels.includes(key)}
                  onChange={() => togglePanel(key)}
                />
                <span>{PANEL_LABELS[key]}</span>
              </label>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="min-h-[28px] rounded border border-white/15 px-2 text-white/60 disabled:opacity-30"
                  disabled={!panels.includes(key) || panels.indexOf(key) === 0}
                  onClick={() => movePanel(key, -1)}
                >
                  Up
                </button>
                <button
                  type="button"
                  className="min-h-[28px] rounded border border-white/15 px-2 text-white/60 disabled:opacity-30"
                  disabled={!panels.includes(key) || panels.indexOf(key) === panels.length - 1}
                  onClick={() => movePanel(key, 1)}
                >
                  Down
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-2 flex h-44 flex-col overflow-hidden rounded border border-cyan-300/15 bg-black/20 p-1" data-testid="workspace-panel-stack">
          {panels.flatMap((key, idx) => {
            const w = weights[key] ?? Math.floor(100 / Math.max(panels.length, 1));
            const tile = (
              <div
                key={`tile-${key}`}
                style={{ flex: `${w} 1 0%`, minHeight: 0 }}
                className="flex min-h-[28px] items-center justify-center rounded border border-cyan-300/20 bg-cyan-400/5 px-2 text-[11px] text-cyan-100"
                data-testid={`workspace-panel-tile-${key}`}
              >
                {PANEL_LABELS[key]} · {w}%
              </div>
            );
            if (idx >= panels.length - 1) return [tile];
            const divider = (
              <div
                key={`div-${idx}`}
                role="separator"
                aria-orientation="horizontal"
                data-testid={`workspace-divider-${idx}`}
                className="group relative z-[1] h-3 shrink-0 cursor-row-resize touch-none"
                onPointerDown={startDividerDrag(idx)}
              >
                <div className="absolute inset-x-6 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-white/25 group-hover:bg-cyan-400/60" />
              </div>
            );
            return [tile, divider];
          })}
        </div>
      </div>

      <textarea
        data-testid="workspace-import-text"
        value={importText}
        onChange={(e) => setImportText(e.target.value)}
        rows={compact ? 3 : 4}
        className="mt-2 w-full rounded border border-white/15 bg-black/25 px-2 py-1.5 font-mono text-[12px] text-white"
        placeholder='{"version":1,"keys":{"qsi_watchlist":"[\"NVDA\"]"}}'
      />
      <button
        type="button"
        data-testid="workspace-import"
        className="mt-2 min-h-[40px] rounded bg-cyan-700 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-cyan-600"
        onClick={importWorkspace}
      >
        Import
      </button>
      {message ? (
        <div className="mt-2 rounded border border-white/10 bg-white/[0.03] px-2 py-1 text-[12px] text-white/70" role="status">
          {message}
        </div>
      ) : null}
    </section>
  );
}
