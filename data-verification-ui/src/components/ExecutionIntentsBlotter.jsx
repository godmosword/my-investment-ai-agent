import { useState } from "react";
import {
  useExecutionIntents,
  useExecutionIntentAllowedStatuses,
  usePatchExecutionIntent,
  getTerminalRefetchIntervalMs,
} from "../hooks/useApi";

const BASE = import.meta.env.VITE_API_URL ?? "";

function statusLabel(s) {
  const map = {
    PENDING_REVIEW: "待審",
    APPROVED_FOR_PAPER: "已核准紙上",
    REJECTED: "已駁回",
    SUPERSEDED: "已取代",
  };
  return map[s] ?? s;
}

export default function ExecutionIntentsBlotter() {
  const pollMs = getTerminalRefetchIntervalMs();
  const { data: rows = [], isLoading, error, isFetching } = useExecutionIntents(50, { livePoll: true });
  const { data: allowedPayload } = useExecutionIntentAllowedStatuses();
  const patch = usePatchExecutionIntent();
  const [notes, setNotes] = useState({});

  const allowed = Array.isArray(allowedPayload?.statuses) ? allowedPayload.statuses : [];

  return (
    <div className="card terminal-blotter">
      <div className="terminal-blotter-header">
        <div>
          <div className="card-title">執行意圖（紙上前置）</div>
          <div className="page-subtitle terminal-blotter-sub">
            輪詢約每 <code>{Math.round(pollMs / 1000)}s</code> · 後端 <code>PATCH</code> 僅 append 狀態，<strong>不下單</strong>
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
        </div>
      )}

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
                  <td>
                    <div className="terminal-blotter-actions">
                      {allowed
                        .filter((s) => s !== row.status)
                        .map((s) => (
                          <button
                            key={s}
                            type="button"
                            className="terminal-btn terminal-btn--small"
                            disabled={patch.isPending}
                            onClick={() =>
                              patch.mutate({
                                signalId: row.signal_id,
                                status: s,
                                note: notes[row.signal_id] ?? "",
                              })
                            }
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
