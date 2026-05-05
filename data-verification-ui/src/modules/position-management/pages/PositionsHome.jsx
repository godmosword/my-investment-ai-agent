import { useExecutionIntents } from "../../../hooks/useApi";

function statusLabel(s) {
  const map = {
    PENDING_REVIEW: "待審",
    APPROVED_FOR_PAPER: "已核准紙上",
    REJECTED: "已駁回",
    SUPERSEDED: "已取代",
  };
  return map[s] ?? s;
}

export default function PositionsHome() {
  const { data: rows = [], isLoading, error } = useExecutionIntents(50, {
    livePoll: false,
    statusFilter: "all",
    categoryFilter: "all",
    sortBy: "updated_desc",
  });

  return (
    <div data-testid="positions-home" className="px-3 py-4 pb-24">
      <h1 className="mb-2 text-lg font-semibold">倉位管理</h1>
      <p className="mb-3 text-[13px] text-[var(--muted)]">
        執行意圖列表（<code>/api/execution-intents</code>）；紙上前置，不下單。
      </p>

      {isLoading && <div className="text-[13px] text-[var(--muted)]">載入中…</div>}
      {error && (
        <div className="error-msg text-[13px]">
          無法載入意圖：<code>{error.message}</code>
        </div>
      )}

      {!isLoading && !error && rows.length === 0 ? (
        <p className="text-[13px] text-[var(--muted)]">目前無意圖列。</p>
      ) : null}

      {!isLoading && !error && rows.length > 0 ? (
        <div className="overflow-x-auto rounded border border-[color:var(--border)]">
          <table className="w-full min-w-[320px] text-left text-[13px]">
            <thead className="bg-[var(--panel)] text-[11px] uppercase text-[var(--muted)]">
              <tr>
                <th className="px-2 py-2">signal_id</th>
                <th className="px-2 py-2">資產</th>
                <th className="px-2 py-2">方向</th>
                <th className="px-2 py-2">狀態</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.signal_id} className="border-t border-[color:var(--border)]">
                  <td className="px-2 py-2 font-mono text-[12px]">{r.signal_id}</td>
                  <td className="px-2 py-2">{r.asset}</td>
                  <td className="px-2 py-2">{r.direction}</td>
                  <td className="px-2 py-2">{statusLabel(r.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
