import { useEffect, useState } from "react";

const WORKSPACE_KEYS = [
  "qsi_watchlist",
  "terminal_recent_symbols",
  "terminal_sse_watch",
  "qs_workspace_layout",
];
const EVENT_KEYS = {
  qsi_watchlist: "qsi_watchlist_changed",
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

export default function WorkspacePanel({ compact = false } = {}) {
  const [layout, setLayout] = useState("balanced");
  const [importText, setImportText] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    try {
      setLayout(globalThis.localStorage?.getItem("qs_workspace_layout") || "balanced");
    } catch {
      setLayout("balanced");
    }
  }, []);

  const updateLayout = (value) => {
    setLayout(value);
    try {
      globalThis.localStorage?.setItem("qs_workspace_layout", value);
    } catch {
      /* ignore */
    }
    setMessage("Workspace layout saved");
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
          <div className="text-[12px] text-[var(--muted)]">local layout · watchlist · recent symbols</div>
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
