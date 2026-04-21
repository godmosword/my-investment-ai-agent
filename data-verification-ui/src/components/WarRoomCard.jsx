/**
 * War Room snapshot: gate failures, scratchpad status, execution intents.
 * Extracted from Today.jsx for reuse and intent status filtering.
 */
export default function WarRoomCard({
  warRoom,
  loading,
  retrying = false,
  error,
  intentStatusFilter = "all",
  onIntentStatusChange,
  onWarRoomRetry,
}) {
  if (loading) {
    return <div className="loading">載入 War Room 快照中…</div>;
  }
  if (error && !warRoom) {
    return (
      <div className="error-msg" style={{ marginBottom: 12 }}>
        無法載入 War Room 快照（<code>/api/war-room/latest</code>）：{error.message}
        {onWarRoomRetry && (
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="war-room-retry"
              disabled={loading}
              onClick={() => onWarRoomRetry()}
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel)",
                color: "var(--text)",
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              重試載入
            </button>
          </div>
        )}
      </div>
    );
  }
  if (!warRoom) {
    return null;
  }

  const intents = Array.isArray(warRoom.execution_intents) ? warRoom.execution_intents : [];
  const u = (s) => (s || "").toUpperCase();
  const filtered =
    intentStatusFilter === "all"
      ? intents
      : intents.filter((it) => u(it.status).includes(u(intentStatusFilter)));

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      {error ? (
        <div className="error-msg" style={{ marginBottom: 10 }} role="status">
          <strong>War Room 快照暫時未更新。</strong> 目前保留上一筆成功資料顯示。
          <div style={{ marginTop: 6 }}>
            <code>/api/war-room/latest</code>：{error.message}
          </div>
        </div>
      ) : null}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div className="card-title" style={{ marginBottom: 0 }}>
          最新健康狀態
        </div>
        {onWarRoomRetry && (
          <button
            type="button"
            className="war-room-retry"
            disabled={loading}
            onClick={() => onWarRoomRetry()}
            style={{
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--panel)",
              color: "var(--muted)",
              cursor: retrying ? "not-allowed" : "pointer",
            }}
          >
            {retrying ? "重試中…" : "重新整理"}
          </button>
        )}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--muted)" }}>
        <div>
          Gate failure：
          <strong style={{ color: "var(--text)" }}>
            {warRoom?.gate_failure?.issue_count ?? 0} 項
          </strong>
        </div>
        <div>
          Scratchpad：
          <strong style={{ color: "var(--text)" }}>
            {warRoom?.scratchpad?.final_status ?? "N/A"}
          </strong>
        </div>
        <div>
          Intents 總數：
          <strong style={{ color: "var(--text)" }}>{intents.length}</strong>
        </div>
      </div>

      {intents.length > 0 && (
        <div style={{ marginTop: 10, marginBottom: 8 }}>
          <span className="section-header subtle" style={{ marginRight: 8 }}>
            Signals 篩選
          </span>
          <select
            aria-label="依 intent 狀態篩選"
            value={intentStatusFilter}
            onChange={(e) => onIntentStatusChange?.(e.target.value)}
            style={{
              fontSize: 12,
              padding: "4px 8px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: "var(--panel)",
              color: "var(--text)",
            }}
          >
            <option value="all">全部（{intents.length}）</option>
            <option value="PENDING">含 PENDING（{intents.filter((it) => u(it.status).includes("PENDING")).length}）</option>
            <option value="REVIEW">含 REVIEW（{intents.filter((it) => u(it.status).includes("REVIEW")).length}）</option>
          </select>
        </div>
      )}

      {filtered.length > 0 ? (
        <>
          <div className="section-header subtle" style={{ marginTop: 12, marginBottom: 8 }}>
            最新 Signals
          </div>
          {filtered
            .slice(-3)
            .reverse()
            .map((it) => (
              <div
                key={`${it.signal_id}-${it.created_at}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 10,
                  fontSize: 12,
                  padding: "8px 0",
                  borderTop: "1px solid var(--border)",
                }}
              >
                <div>
                  <strong>{it.asset}</strong> {it.direction}
                  <div style={{ color: "var(--muted)" }}>
                    {it.category} / {it.regime || "neutral"}
                  </div>
                </div>
                <div style={{ textAlign: "right", color: "var(--muted)" }}>
                  <div>{it.status || "PENDING_REVIEW"}</div>
                  <div>{it.star_rating}★</div>
                </div>
              </div>
            ))}
        </>
      ) : (
        intents.length > 0 && (
          <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 10 }}>
            目前篩選下無符合項目；請改選「全部」或確認後端 status 欄位。
          </p>
        )
      )}
    </div>
  );
}
