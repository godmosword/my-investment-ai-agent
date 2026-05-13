import { useEffect, useMemo, useState } from "react";
import {
  useIndustryThemes,
  usePaperLifecycle,
  usePortfolioPnl,
  usePriceAlerts,
} from "../hooks/useApi";

const WORKSPACE_KEYS = [
  "qsi_watchlist",
  "terminal_recent_symbols",
  "terminal_sse_watch",
  "qs_workspace_layout",
  "qs_workspace_panels",
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

  useEffect(() => {
    try {
      setLayout(globalThis.localStorage?.getItem("qs_workspace_layout") || "balanced");
    } catch {
      setLayout("balanced");
    }
    setPanels(readPanels());
  }, []);

  const digest = useMemo(() => {
    const alertRows = alerts.data?.alerts ?? [];
    const themeRows = themes.data?.themes ?? [];
    return {
      portfolioValue: portfolio.data?.total_value,
      portfolioPnl: portfolio.data?.total_pnl,
      paperActive: paper.data?.summary?.active_count ?? 0,
      paperClosed: paper.data?.summary?.closed_count ?? 0,
      topTheme: themeRows[0]?.label || "—",
      alertsTotal: alertRows.length,
      alertsTriggered: alertRows.filter((item) => item.triggered_at).length,
    };
  }, [alerts.data, paper.data, portfolio.data, themes.data]);

  const updateLayout = (value) => {
    setLayout(value);
    try {
      globalThis.localStorage?.setItem("qs_workspace_layout", value);
    } catch {
      /* ignore */
    }
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
        <div className={`mt-2 grid gap-1 ${layout === "dense" ? "grid-cols-2" : "grid-cols-1"}`}>
          {panels.map((key) => (
            <div key={key} className="rounded border border-cyan-300/20 bg-cyan-400/5 px-2 py-1 text-[11px] text-cyan-100">
              {PANEL_LABELS[key]}
            </div>
          ))}
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
