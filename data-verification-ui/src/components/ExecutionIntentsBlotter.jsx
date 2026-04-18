import { useState } from "react";
import {
  useExecutionIntents,
  useExecutionIntentAllowedStatuses,
  usePatchExecutionIntent,
  getTerminalRefetchIntervalMs,
} from "../hooks/useApi";

const BASE = import.meta.env.VITE_API_URL ?? "";
const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";
const SSE_KEY = import.meta.env.VITE_SSE_STREAM_KEY ?? "";

function statusLabel(s) {
  const map = {
    PENDING_REVIEW: "待審",
    APPROVED_FOR_PAPER: "已核准紙上",
    REJECTED: "已駁回",
    SUPERSEDED: "已取代",
    PAPER_SUBMITTED: "紙上已排程",
    PAPER_FILLED: "紙上已成交",
    PAPER_CLOSED: "紙上已平倉",
  };
  return map[s] ?? s;
}

export default function ExecutionIntentsBlotter() {
  const pollMs = getTerminalRefetchIntervalMs();
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortBy, setSortBy] = useState("updated_desc");
  const {
    data: rows = [],
    isLoading,
    error,
    isFetching,
    refetch,
  } = useExecutionIntents(50, {
    livePoll: true,
    statusFilter,
    categoryFilter,
    sortBy,
  });
  const { data: allowedPayload } = useExecutionIntentAllowedStatuses();
  const patch = usePatchExecutionIntent();
  const [notes, setNotes] = useState({});
  /** 紙上模擬用參考價（僅在轉為「已核准紙上」時一併送出） */
  const [refs, setRefs] = useState({});

  const clientPatchable = Array.isArray(allowedPayload?.client_patchable)
    ? allowedPayload.client_patchable
    : ["PENDING_REVIEW", "APPROVED_FOR_PAPER", "REJECTED", "SUPERSEDED"];

  const setRefField = (signalId, field, value) => {
    setRefs((prev) => ({
      ...prev,
      [signalId]: { ...(prev[signalId] || {}), [field]: value },
    }));
  };

  return (
    <div className="card terminal-blotter">
      <div className="terminal-blotter-header">
        <div>
          <div className="card-title">執行意圖（紙上前置）</div>
          <div className="page-subtitle terminal-blotter-sub">
            輪詢約每 <code>{Math.round(pollMs / 1000)}s</code>
            {SSE_ENABLED && BASE ? (
              <span>
                {" "}
                · <code>SSE</code> 已啟用（<code>VITE_SSE_ENABLED=1</code>，後端需 <code>TERMINAL_SSE_ENABLED=1</code>）
              </span>
            ) : null}
            {" "}
            · 後端 <code>PATCH</code> 僅 append 狀態，<strong>不下單</strong>
            {!BASE ? (
              <span className="terminal-blotter-warn"> · 未設定 <code>VITE_API_URL</code> 時無法操作</span>
            ) : null}
          </div>
        </div>
        {isFetching && !isLoading ? <span className="terminal-blotter-sync">更新中…</span> : null}
      </div>

      {isLoading && <div className="loading">載入意圖列表…</div>}
      {error && (
        <div className="error-msg">
          無法載入 <code>/api/execution-intents</code>：{error.message}
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="terminal-btn terminal-btn--small"
              disabled={isFetching}
              onClick={() => refetch()}
            >
              {isFetching ? "重試中…" : "重試載入"}
            </button>
          </div>
        </div>
      )}

      {!isLoading && !error ? (
        <div className="terminal-blotter-filters" style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          <label className="page-subtitle" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            狀態
            <select
              className="terminal-input terminal-input--narrow"
              style={{ minWidth: 140 }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">全部</option>
              <option value="PENDING">待審（PENDING…）</option>
              <option value="APPROVED">已核准紙上</option>
              <option value="REJECTED">已駁回</option>
              <option value="PAPER">紙上生命週期</option>
            </select>
          </label>
          <label className="page-subtitle" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            類別
            <select
              className="terminal-input terminal-input--narrow"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="all">全部</option>
              <option value="CRYPTO">CRYPTO</option>
              <option value="AI">AI</option>
            </select>
          </label>
          <label className="page-subtitle" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            排序
            <select
              className="terminal-input terminal-input--narrow"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="updated_desc">最近更新</option>
              <option value="created_desc">建立時間</option>
              <option value="asset_asc">代號 A→Z</option>
            </select>
          </label>
        </div>
      ) : null}

      {!isLoading && !error && rows.length === 0 ? (
        <div className="page-subtitle">目前無執行意圖（或 JSONL 為空）。管線寫入後將顯示於此。</div>
      ) : null}

      {!isLoading && !error && rows.length > 0 ? (
        <div className="terminal-blotter-table-wrap">
          <table className="terminal-blotter-table">
            <thead>
              <tr>
                <th>資產</th>
                <th>方向</th>
                <th>狀態</th>
                <th>建立</th>
                <th>參考價（紙上）</th>
                <th>操作</th>
                <th>備註</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.signal_id}>
                  <td>
                    <strong>{row.asset}</strong>
                    <div className="terminal-blotter-id">{row.signal_id}</div>
                    {Array.isArray(row.gate_issue_hints) && row.gate_issue_hints.length > 0 ? (
                      <div className="terminal-blotter-note-read" style={{ marginTop: 4, fontSize: 11 }}>
                        Gate 關聯：{row.gate_issue_hints[0]}
                        {row.gate_issue_hints.length > 1 ? `（+${row.gate_issue_hints.length - 1}）` : ""}
                      </div>
                    ) : null}
                  </td>
                  <td>{row.direction}</td>
                  <td>
                    <span className="terminal-blotter-status">{statusLabel(row.status)}</span>
                    {row.status_note ? (
                      <div className="terminal-blotter-note-read">{row.status_note}</div>
                    ) : null}
                  </td>
                  <td className="terminal-blotter-date">
                    {row.created_at ? new Date(row.created_at).toLocaleString("zh-TW") : "—"}
                  </td>
                  <td className="terminal-blotter-refs">
                    <div className="terminal-blotter-ref-grid">
                      <label>
                        entry
                        <input
                          type="text"
                          inputMode="decimal"
                          className="terminal-blotter-ref-input"
                          placeholder="—"
                          value={
                            refs[row.signal_id]?.entry ??
                            (row.reference_entry_price != null ? String(row.reference_entry_price) : "")
                          }
                          onChange={(e) => setRefField(row.signal_id, "entry", e.target.value)}
                        />
                      </label>
                      <label>
                        target
                        <input
                          type="text"
                          inputMode="decimal"
                          className="terminal-blotter-ref-input"
                          placeholder="—"
                          value={
                            refs[row.signal_id]?.target ??
                            (row.reference_target_price != null ? String(row.reference_target_price) : "")
                          }
                          onChange={(e) => setRefField(row.signal_id, "target", e.target.value)}
                        />
                      </label>
                      <label>
                        stop
                        <input
                          type="text"
                          inputMode="decimal"
                          className="terminal-blotter-ref-input"
                          placeholder="—"
                          value={
                            refs[row.signal_id]?.stop ??
                            (row.reference_stop_price != null ? String(row.reference_stop_price) : "")
                          }
                          onChange={(e) => setRefField(row.signal_id, "stop", e.target.value)}
                        />
                      </label>
                    </div>
                    <div className="terminal-blotter-ref-hint">核准紙上時一併送出，供紙上 tick 比對</div>
                  </td>
                  <td>
                    <div className="terminal-blotter-actions">
                      {clientPatchable
                        .filter((s) => s !== row.status)
                        .map((s) => (
                          <button
                            key={s}
                            type="button"
                            className="terminal-btn terminal-btn--small"
                            disabled={patch.isPending}
                            onClick={() => {
                              const r = refs[row.signal_id] || {};
                              const parseNum = (v) => {
                                const t = (v ?? "").trim();
                                if (!t) return null;
                                const n = Number(t);
                                return Number.isFinite(n) ? n : null;
                              };
                              patch.mutate({
                                signalId: row.signal_id,
                                status: s,
                                note: notes[row.signal_id] ?? "",
                                reference_entry_price:
                                  s === "APPROVED_FOR_PAPER" ? parseNum(r.entry) : undefined,
                                reference_target_price:
                                  s === "APPROVED_FOR_PAPER" ? parseNum(r.target) : undefined,
                                reference_stop_price:
                                  s === "APPROVED_FOR_PAPER" ? parseNum(r.stop) : undefined,
                              });
                            }}
                          >
                            → {statusLabel(s)}
                          </button>
                        ))}
                    </div>
                  </td>
                  <td>
                    <textarea
                      className="terminal-blotter-note-input"
                      rows={2}
                      placeholder="狀態變更備註（可選）"
                      value={notes[row.signal_id] ?? ""}
                      onChange={(e) =>
                        setNotes((prev) => ({ ...prev, [row.signal_id]: e.target.value }))
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {patch.isError ? (
            <div className="error-msg terminal-blotter-mut-err" role="alert">
              狀態更新失敗：{patch.error?.message ?? "未知錯誤"}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
