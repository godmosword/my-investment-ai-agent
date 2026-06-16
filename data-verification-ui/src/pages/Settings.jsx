import { useEffect, useRef, useState } from "react";
import { useGateFailures, useQsrecStats } from "../hooks/useApi";

const PREFS_KEY = "qsilicon_push_prefs";
const POLL_OVERRIDE_KEY = "qs_terminal_poll_ms_override";
const POLL_OPTIONS = [
  { value: "15000", label: "15s（高頻）" },
  { value: "45000", label: "45s（預設）" },
  { value: "120000", label: "2 分鐘（低頻）" },
];

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
  const [healthOkAt, setHealthOkAt] = useState("");
  const [healthErr, setHealthErr] = useState("");
  const [selectedGateFailure, setSelectedGateFailure] = useState(null);
  const [pollOverride, setPollOverride] = useState(() => {
    try {
      return globalThis.localStorage?.getItem(POLL_OVERRIDE_KEY) || "";
    } catch {
      return "";
    }
  });
  const importRef = useRef(null);
  const gateDrawerRef = useRef(null);
  const gateCloseRef = useRef(null);
  const qsrecStats = useQsrecStats(7);
  const gateFailures = useGateFailures(7);

  const pushRegister = envFlag(import.meta.env.VITE_WEB_PUSH_REGISTER);
  const vapidSet = Boolean(String(import.meta.env.VITE_WEB_PUSH_VAPID_PUBLIC_KEY || "").trim());
  const apiUrl = String(import.meta.env.VITE_API_URL || "").trim();
  const sseEnabled = envFlag(import.meta.env.VITE_SSE_ENABLED);
  const sseStreamKeySet = Boolean(String(import.meta.env.VITE_SSE_STREAM_KEY || "").trim());
  const structuredReport = envFlag(import.meta.env.VITE_STRUCTURED_REPORT);

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
    if (!selectedGateFailure) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") setSelectedGateFailure(null);
    };
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [selectedGateFailure]);

  useEffect(() => {
    const base = String(import.meta.env.VITE_API_URL || "").trim().replace(/\/$/, "");
    if (!base) {
      setHealthErr("未設定 VITE_API_URL，無法探活");
      return undefined;
    }
    let cancelled = false;
    const ping = () => {
      fetch(`${base}/healthz`, { method: "GET", cache: "no-store" })
        .then((r) => {
          if (cancelled) return;
          if (r.ok) {
            setHealthOkAt(new Date().toISOString());
            setHealthErr("");
          } else {
            setHealthErr(`HTTP ${r.status}`);
          }
        })
        .catch((e) => {
          if (!cancelled) setHealthErr(e instanceof Error ? e.message : String(e));
        });
    };
    ping();
    const id = globalThis.setInterval(ping, 60_000);
    return () => {
      cancelled = true;
      globalThis.clearInterval(id);
    };
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

  const choosePoll = (value) => {
    setPollOverride(value);
    try {
      if (value) globalThis.localStorage?.setItem(POLL_OVERRIDE_KEY, value);
      else globalThis.localStorage?.removeItem(POLL_OVERRIDE_KEY);
    } catch {
      /* ignore */
    }
  };

  const passRatePct = qsrecStats.data?.pass_rate_pct;
  const passRateText =
    qsrecStats.isLoading
      ? "…"
      : typeof passRatePct === "number"
        ? `${passRatePct.toFixed(1)}%`
        : "—";

  return (
    <div className="settings-page px-3 py-4 pb-24">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">設定</h1>
      <p className="mb-4 text-[13px] text-[var(--muted)]">
        Web Push、Service Worker 與訂閱 metadata（與{" "}
        <code className="rounded bg-black/25 px-1 py-0.5 font-mono text-[11px]">pushClient.js</code>{" "}
        對齊）。
      </p>

      <div className="settings-grid" data-testid="settings-grid">
        <section className="card p-3" data-testid="settings-gate-stats">
          <h2 className="mb-2 text-[13px] font-semibold">Gate 通過率（近 7 天）</h2>
          <p className="m-0 text-[12px] text-[var(--muted)]">
            來自 <code className="font-mono text-[11px]">GET /api/reports/qsrec-stats?days=7</code>
          </p>
          <div className="mt-2 flex flex-wrap items-baseline gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">通過率</div>
              <div className="text-[20px] font-bold text-emerald-300" data-testid="settings-pass-rate">
                {passRateText}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">統計天數</div>
              <div className="font-mono text-[14px]">{qsrecStats.data?.total_days ?? "—"}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Degraded</div>
              <div className="font-mono text-[14px]">{qsrecStats.data?.degraded_count ?? "—"}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Fail</div>
              <div className="font-mono text-[14px]">{qsrecStats.data?.fail_count ?? "—"}</div>
            </div>
          </div>
        </section>

        <section className="card p-3" data-testid="settings-poll-toggle">
          <h2 className="mb-2 text-[13px] font-semibold">盤中輪詢頻率</h2>
          <p className="m-0 text-[12px] text-[var(--muted)]">
            覆寫 <code className="font-mono text-[11px]">VITE_TERMINAL_POLL_MS</code>（預設 45s）；存於
            <code className="font-mono text-[11px]"> localStorage[{POLL_OVERRIDE_KEY}]</code>，下次載入生效。
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {POLL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                data-testid={`settings-poll-${opt.value}`}
                aria-pressed={pollOverride === opt.value}
                className={`min-h-[44px] rounded border px-3 py-1.5 text-[12px] font-semibold ${
                  pollOverride === opt.value
                    ? "border-emerald-500/40 bg-emerald-500/[0.10] text-emerald-100/90"
                    : "border-white/15 text-white/70 hover:bg-white/[0.04]"
                }`}
                onClick={() => choosePoll(opt.value)}
              >
                {opt.label}
              </button>
            ))}
            <button
              type="button"
              data-testid="settings-poll-clear"
              className="min-h-[44px] rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/60 hover:bg-white/[0.04]"
              onClick={() => choosePoll("")}
            >
              使用預設
            </button>
          </div>
        </section>

        <section className="card p-3" data-testid="settings-gate-failures">
          <h2 className="mb-1 text-[13px] font-semibold">Gate 失敗記錄（近 7 天）</h2>
          <p className="mb-2 text-[12px] text-[var(--muted)]">
            <code className="font-mono text-[11px]">GET /api/gate-failures?days=7</code>
            {gateFailures.data?.source ? (
              <span className="ml-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                source: {gateFailures.data.source}
              </span>
            ) : null}
          </p>
          {gateFailures.isLoading ? (
            <p className="m-0 text-[12px] text-[var(--muted)]">載入中…</p>
          ) : gateFailures.isError ? (
            <p className="m-0 text-[12px] text-amber-300" role="status">
              {gateFailures.error?.message ?? "載入失敗"}
            </p>
          ) : !gateFailures.data?.entries?.length ? (
            <p className="m-0 text-[12px] text-[var(--muted)]">近 7 天無 Gate 失敗紀錄。</p>
          ) : (
            <ul
              className="m-0 list-none space-y-1 p-0 font-mono text-[11px]"
              data-testid="settings-gate-failures-list"
            >
              {gateFailures.data.entries.slice(0, 5).map((row, i) => (
                <li key={`${row.timestamp ?? "row"}-${i}`}>
                  <button
                    type="button"
                    className="min-h-[44px] w-full rounded border border-white/10 bg-black/15 px-2 py-1.5 text-left hover:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-cyan-400/50"
                    data-testid="settings-gate-failure-row"
                    onClick={() => setSelectedGateFailure(row)}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[var(--muted)]">{(row.timestamp ?? "").slice(0, 19)}</span>
                      <span className="rounded bg-amber-500/10 px-1.5 text-amber-200">
                        profile: {row.profile ?? "—"}
                      </span>
                      <span className="rounded bg-red-500/10 px-1.5 text-red-200">
                        blocking: {row.blocking_count ?? 0}
                      </span>
                      <span className="rounded bg-yellow-500/10 px-1.5 text-yellow-200">
                        warn: {row.warning_count ?? 0}
                      </span>
                    </div>
                    {row.issues_preview ? (
                      <div className="mt-1 text-white/75">{row.issues_preview}</div>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {selectedGateFailure ? (
        <div className="fixed inset-0 z-50 flex items-end bg-black/60 p-2 sm:items-center sm:justify-end sm:p-4">
          <section
            ref={gateDrawerRef}
            className="max-h-[88vh] w-full overflow-auto rounded-lg border border-white/15 bg-[var(--bg,#05070a)] p-4 shadow-2xl sm:max-w-md"
            data-testid="settings-gate-failure-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Gate failure detail"
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h2 className="m-0 text-[14px] font-semibold">Gate failure detail</h2>
                <p className="m-0 mt-1 font-mono text-[11px] text-[var(--muted)]">
                  {selectedGateFailure.timestamp ?? "—"}
                </p>
              </div>
              <button
                ref={gateCloseRef}
                type="button"
                className="min-h-[44px] rounded border border-white/15 px-3 text-[12px] text-white/70 hover:text-white"
                data-testid="settings-gate-failure-drawer-close"
                onClick={() => setSelectedGateFailure(null)}
              >
                Close
              </button>
            </div>
            <div className="mb-3 flex flex-wrap gap-2 font-mono text-[11px]">
              <span className="rounded bg-white/5 px-2 py-1">attempt: {selectedGateFailure.attempt ?? "—"}</span>
              <span className="rounded bg-amber-500/10 px-2 py-1 text-amber-200">
                profile: {selectedGateFailure.profile ?? "—"}
              </span>
              <span className="rounded bg-red-500/10 px-2 py-1 text-red-200">
                blocking: {selectedGateFailure.blocking_count ?? 0}
              </span>
              <span className="rounded bg-yellow-500/10 px-2 py-1 text-yellow-200">
                warn: {selectedGateFailure.warning_count ?? 0}
              </span>
              <span className="rounded bg-cyan-500/10 px-2 py-1 text-cyan-200">
                issues: {selectedGateFailure.issue_count ?? 0}
              </span>
              <span className="rounded bg-white/5 px-2 py-1">
                fallback: {selectedGateFailure.used_fallback ? "yes" : "no"}
              </span>
            </div>
            <div className="rounded border border-white/10 bg-black/20 p-3">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--muted)]">issues_preview</div>
              <p className="m-0 whitespace-pre-wrap text-[12px] leading-relaxed text-white/80">
                {selectedGateFailure.issues_preview || "—"}
              </p>
            </div>
          </section>
        </div>
      ) : null}

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
            VITE_TECH_PULSE_URL:{" "}
            <span className={String(import.meta.env.VITE_TECH_PULSE_URL || "").trim() ? "text-emerald-200/90" : "text-[var(--muted)]"}>
              {String(import.meta.env.VITE_TECH_PULSE_URL || "").trim() || "未設定"}
            </span>
          </li>
          <li>
            VITE_API_URL:{" "}
            <span className={apiUrl ? "text-emerald-200/90" : "text-amber-300"}>
              {apiUrl || "未設定"}
            </span>
          </li>
          <li>
            VITE_SSE_ENABLED:{" "}
            <span className={sseEnabled ? "text-emerald-300" : "text-[var(--muted)]"}>
              {sseEnabled ? "1（啟用）" : "未啟用"}
            </span>
          </li>
          <li>
            VITE_SSE_STREAM_KEY:{" "}
            <span className={sseStreamKeySet ? "text-emerald-300" : "text-amber-300"}>
              {sseStreamKeySet ? "已設定" : "未設定"}
            </span>
          </li>
          <li>
            VITE_STRUCTURED_REPORT:{" "}
            <span className={structuredReport ? "text-emerald-300" : "text-[var(--muted)]"}>
              {structuredReport ? "1（啟用）" : "未啟用"}
            </span>
          </li>
        </ul>
      </section>

      <section className="card mb-4 p-3">
        <h2 className="mb-2 text-[13px] font-semibold">API 探活（GET /healthz）</h2>
        <p className="m-0 text-[12px] text-[var(--muted)]">
          基底：<code className="font-mono text-[11px]">{apiUrl || "—"}</code>
        </p>
        {healthOkAt ? (
          <p className="mt-1 mb-0 text-[12px] text-emerald-300">
            最後成功：<span className="font-mono">{healthOkAt}</span>
          </p>
        ) : null}
        {healthErr ? (
          <p className="mt-1 mb-0 text-[12px] text-amber-300" role="status">
            {healthErr}
          </p>
        ) : null}
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
          <span className="font-semibold text-[var(--fg)]">投資觀點</span> canonical 路徑為 <code className="font-mono">/insights</code>；<code className="font-mono">/briefs</code> 與 <code className="font-mono">/terminal</code> 會相容導向此頁。五板塊導覽見頂欄 Shell。
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
