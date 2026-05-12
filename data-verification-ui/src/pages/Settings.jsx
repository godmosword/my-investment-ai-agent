import { useEffect, useRef, useState } from "react";

const PREFS_KEY = "qsilicon_push_prefs";

// Workspace keys to include in export/import (Q34)
const WORKSPACE_KEYS = [
  "qs_workspace_layout",
  "terminal_sse_watch",
  "terminal_recent_symbols",
];

function exportWorkspace() {
  const data = {};
  for (const k of WORKSPACE_KEYS) {
    try {
      const v = globalThis.localStorage?.getItem(k);
      if (v != null) data[k] = v;
    } catch { /* ignore */ }
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `qs-workspace-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importWorkspace(json) {
  const data = JSON.parse(json);
  let count = 0;
  for (const k of WORKSPACE_KEYS) {
    if (Object.prototype.hasOwnProperty.call(data, k) && typeof data[k] === "string") {
      globalThis.localStorage?.setItem(k, data[k]);
      count++;
    }
  }
  return count;
}

function envFlag(v) {
  const s = String(v ?? "").trim().toLowerCase();
  return s === "1" || s === "true";
}

export default function Settings() {
  const [swState, setSwState] = useState("—");
  const [reportDate, setReportDate] = useState("");
  const [blockId, setBlockId] = useState("");
  const [savedHint, setSavedHint] = useState("");
  const [workspaceHint, setWorkspaceHint] = useState("");
  const importRef = useRef(null);

  const pushRegister = envFlag(import.meta.env.VITE_WEB_PUSH_REGISTER);
  const vapidSet = Boolean(String(import.meta.env.VITE_WEB_PUSH_VAPID_PUBLIC_KEY || "").trim());
  const apiUrl = String(import.meta.env.VITE_API_URL || "").trim();

  useEffect(() => {
    if (!("serviceWorker" in navigator)) {
      setSwState("不支援");
      return;
    }
    navigator.serviceWorker.getRegistration().then((reg) => {
      setSwState(reg ? "已註冊" : "未註冊");
    });
  }, []);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(PREFS_KEY);
      if (!raw) return;
      const p = JSON.parse(raw);
      if (p && typeof p === "object") {
        if (p.report_date) setReportDate(String(p.report_date));
        if (p.block_id) setBlockId(String(p.block_id));
      }
    } catch {
      /* ignore */
    }
  }, []);

  const savePushPrefs = () => {
    const o = {};
    if (reportDate.trim()) o.report_date = reportDate.trim();
    if (blockId.trim()) o.block_id = blockId.trim();
    try {
      sessionStorage.setItem(PREFS_KEY, JSON.stringify(o));
      setSavedHint("已儲存至 sessionStorage（下次 push subscribe 會帶入）");
      setTimeout(() => setSavedHint(""), 3500);
    } catch (e) {
      setSavedHint(`儲存失敗：${e?.message || e}`);
    }
  };

  return (
    <div className="settings-page px-3 py-4 pb-24">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">設定</h1>
      <p className="mb-4 text-[13px] text-[var(--muted)]">
        Web Push、Service Worker 與訂閱 metadata（與{" "}
        <code className="rounded bg-black/25 px-1 py-0.5 font-mono text-[11px]">pushClient.js</code>{" "}
        對齊）。
      </p>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">建置環境（唯讀）</h2>
        <ul className="m-0 list-none space-y-1 p-0 text-[12px] font-mono">
          <li>
            VITE_WEB_PUSH_REGISTER:{" "}
            <span className={pushRegister ? "text-emerald-300" : "text-[var(--muted)]"}>
              {pushRegister ? "1（啟用）" : "未啟用"}
            </span>
          </li>
          <li>
            VITE_WEB_PUSH_VAPID_PUBLIC_KEY:{" "}
            <span className={vapidSet ? "text-emerald-300" : "text-amber-300"}>
              {vapidSet ? "已設定" : "未設定"}
            </span>
          </li>
          <li>
            VITE_API_URL:{" "}
            <span className={apiUrl ? "text-emerald-200/90" : "text-amber-300"}>
              {apiUrl || "未設定"}
            </span>
          </li>
        </ul>
      </section>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">Service Worker</h2>
        <p className="m-0 text-[12px] text-[var(--muted)]">
          狀態：<span className="text-emerald-200/90">{swState}</span>
        </p>
      </section>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">Portal／日報路由</h2>
        <p className="mb-2 text-[12px] leading-snug text-[var(--muted)]">
          <span className="font-semibold text-[var(--fg)]">日報</span> canonical 路徑為 <code className="font-mono">/briefs</code>；<code className="font-mono">/terminal</code> 與其同頁（相容既有連結與 E2E）。五模組導覽見頂欄 Shell。
        </p>
        <p className="m-0 text-[11px] leading-snug text-[var(--muted)]">
          API 基底與選用主金鑰：<code className="font-mono">VITE_API_URL</code>、<code className="font-mono">VITE_QSILICON_KEY</code>（送 <code className="font-mono">X-Q-Silicon-Key</code>；401 觸發全域事件）。
        </p>
      </section>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">圖表／對齊（後端 Runbook）</h2>
        <p className="m-0 text-[12px] leading-snug text-[var(--muted)]">
          BTC Panel 1 收盤序列來源由伺服端 <code className="font-mono">VISUALIZER_BTC_SOURCE</code> 控制（<code className="font-mono">yfinance</code> 預設；<code className="font-mono">snapshot</code> 時改吃已驗證之
          <code className="font-mono">symbol_snapshot</code> <code className="font-mono">price_series</code>，須 BQ 可用）。本頁不讀該變數，僅供溯源說明；詳見{" "}
          <code className="rounded bg-black/25 px-1 py-0.5 font-mono text-[11px]">docs/DASHBOARD_CONTRACT.md</code> 與{" "}
          <code className="rounded bg-black/25 px-1 py-0.5 font-mono text-[11px]">docs/architecture/visualization_plan.md</code>。
        </p>
      </section>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">Push 訂閱 metadata（sessionStorage）</h2>
        <p className="mb-2 text-[11px] leading-snug text-[var(--muted)]">
          鍵名 <code className="font-mono">{PREFS_KEY}</code>，會與{" "}
          <code className="font-mono">VITE_PUSH_SUBSCRIBE_*</code> 合併後送{" "}
          <code className="font-mono">POST /api/push/subscribe</code>。
        </p>
        <label className="mb-2 block text-[11px] text-[var(--muted)]">
          report_date（YYYY-MM-DD）
          <input
            type="text"
            className="mt-1 w-full rounded border border-[color:var(--border)] bg-black/20 px-2 py-1.5 font-mono text-[12px]"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            placeholder="例如 2026-04-18"
          />
        </label>
        <label className="mb-2 block text-[11px] text-[var(--muted)]">
          block_id
          <input
            type="text"
            className="mt-1 w-full rounded border border-[color:var(--border)] bg-black/20 px-2 py-1.5 font-mono text-[12px]"
            value={blockId}
            onChange={(e) => setBlockId(e.target.value)}
            placeholder="例如 exec_summary"
          />
        </label>
        <button
          type="button"
          className="rounded bg-emerald-700/80 px-3 py-1.5 text-[12px] font-medium text-white"
          onClick={savePushPrefs}
        >
          儲存偏好
        </button>
        {savedHint ? <p className="mt-2 mb-0 text-[11px] text-emerald-300">{savedHint}</p> : null}
      </section>

      {/* Workspace export/import (Q34) */}
      <section className="card mb-4 p-3" data-testid="workspace-section">
        <h2 className="mb-1 text-[13px] font-semibold">工作區匯出 / 匯入（Q34）</h2>
        <p className="mb-3 text-[11px] leading-snug text-[var(--muted)]">
          序列化 <code className="font-mono">terminal_sse_watch</code>、<code className="font-mono">terminal_recent_symbols</code>、<code className="font-mono">qs_workspace_layout</code> 為 JSON 檔案，可跨裝置還原。
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="workspace-export-btn"
            className="rounded border border-emerald-500/40 bg-emerald-600/20 px-3 py-1.5 text-[12px] font-medium text-emerald-300 hover:bg-emerald-600/40"
            onClick={() => {
              try {
                exportWorkspace();
                setWorkspaceHint("已匯出工作區 JSON");
                setTimeout(() => setWorkspaceHint(""), 3500);
              } catch (e) {
                setWorkspaceHint(`匯出失敗：${e?.message ?? e}`);
              }
            }}
          >
            匯出工作區
          </button>
          <button
            type="button"
            data-testid="workspace-import-btn"
            className="rounded border border-white/20 px-3 py-1.5 text-[12px] font-medium text-white/70 hover:bg-white/5"
            onClick={() => importRef.current?.click()}
          >
            匯入工作區
          </button>
          <input
            ref={importRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            data-testid="workspace-import-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = (ev) => {
                try {
                  const count = importWorkspace(String(ev.target?.result ?? ""));
                  setWorkspaceHint(`已匯入 ${count} 個工作區設定`);
                  setTimeout(() => setWorkspaceHint(""), 3500);
                } catch (err) {
                  setWorkspaceHint(`匯入失敗：${err?.message ?? err}`);
                }
                // Reset so the same file can be re-imported
                e.target.value = "";
              };
              reader.readAsText(file);
            }}
          />
        </div>
        {workspaceHint ? (
          <p className="mt-2 mb-0 text-[11px] text-emerald-300" role="status">{workspaceHint}</p>
        ) : null}
      </section>

      <section className="card p-3">
        <h2 className="mb-2 text-[13px] font-semibold">說明文件</h2>
        <p className="m-0 text-[12px] text-[var(--muted)]">
          完整設定請見專案根目錄{" "}
          <code className="rounded bg-black/25 px-1 py-0.5 font-mono text-[11px]">docs/PWA_WEB_PUSH.md</code>
          。
        </p>
      </section>
    </div>
  );
}
