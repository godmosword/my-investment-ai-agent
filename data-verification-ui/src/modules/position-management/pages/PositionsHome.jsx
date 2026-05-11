import { useExecutionIntents, usePositionsList } from "../../../hooks/useApi";

function finiteNumber(value) {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function paperEntry(r) {
  return finiteNumber(r.paper_fill_price ?? r.paper_entry ?? r.reference_entry_price ?? r.entry_price);
}

function paperExit(r) {
  return finiteNumber(r.paper_exit_price ?? r.paper_exit);
}

function isPaperClosedRow(r) {
  const s = String(r.status ?? "").toUpperCase();
  return s === "PAPER_CLOSED" || s === "CLOSED" || s === "EXITED";
}

function calcStats(rows) {
  if (!rows || rows.length === 0) return null;
  const closed = rows.filter(isPaperClosedRow);
  const settled = closed.filter((r) => {
    const px = paperExit(r);
    const en = paperEntry(r);
    return px != null && en != null && en !== 0;
  });
  if (settled.length === 0) return null;

  const wins = settled.filter((r) => {
    const px = paperExit(r);
    const en = paperEntry(r);
    const dir = (r.direction ?? "").toUpperCase();
    if (dir !== "LONG" && dir !== "SHORT") return false;
    return dir === "LONG" ? px > en : px < en;
  });

  const winRate = settled.length > 0 ? Math.round((wins.length / settled.length) * 100) : 0;

  const pnls = settled
    .map((r) => {
      const px = paperExit(r);
      const en = paperEntry(r);
      const dir = (r.direction ?? "").toUpperCase();
      if (dir !== "LONG" && dir !== "SHORT") return null;
      const raw = dir === "LONG" ? (px - en) / en : (en - px) / en;
      return raw * 100;
    })
    .filter((v) => Number.isFinite(v));

  const avgPnl = pnls.length > 0 ? pnls.reduce((a, b) => a + b, 0) / pnls.length : 0;

  return { total: settled.length, wins: wins.length, winRate, avgPnl: avgPnl.toFixed(2) };
}

function StatsPill({ label, value, color }) {
  return (
    <div style={{ textAlign: "center", minWidth: 72 }}>
      <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color ?? "var(--text)", marginTop: 2 }}>{value}</div>
    </div>
  );
}

/** Entry→Exit arrow for closed positions only. Only renders when both prices are non-null. */
function PnLArrow({ row }) {
  const en = paperEntry(row);
  const ex = paperExit(row);
  // Defensive null check — never render for open positions
  if (en == null || ex == null) return null;

  const dir = (row.direction ?? "").toUpperCase();
  const isWin = dir === "LONG" ? ex > en : dir === "SHORT" ? ex < en : false;
  const color = isWin ? "var(--green, #22c55e)" : "var(--red, #ef4444)";
  const pct = en !== 0 ? (((dir === "LONG" ? ex - en : en - ex) / en) * 100).toFixed(1) : null;

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, color }}>
      {en.toFixed(2)} → {ex.toFixed(2)}
      {pct != null && <span style={{ fontWeight: 600 }}>({isWin ? "+" : ""}{pct}%)</span>}
    </span>
  );
}

function statusLabel(s) {
  const map = {
    PENDING_REVIEW: "待審",
    APPROVED_FOR_PAPER: "已核准紙上",
    REJECTED: "已駁回",
    SUPERSEDED: "已取代",
    PAPER_CLOSED: "已結倉",
    CLOSED: "已結倉",
    EXITED: "已結倉",
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

  const {
    data: openRecs = [],
    isLoading: posLoading,
    error: posError,
  } = usePositionsList(90, "OPEN");

  const stats = calcStats(rows);

  return (
    <div data-testid="positions-home" className="px-3 py-4 pb-24">
      <h1 className="mb-2 text-lg font-semibold">倉位管理</h1>
      <p className="mb-3 text-[13px] text-[var(--muted)]">
        執行意圖（<code>/api/execution-intents</code>）與 OPEN 建議聚合（<code>/api/positions</code>，M4）；紙上前置，不下單。
      </p>

      <h2 className="mb-1 text-[14px] font-semibold text-white/90">OPEN 建議（M4）</h2>
      <p className="mb-2 text-[12px] text-[var(--muted)]">
        與 <code>/api/positions/open</code> 同源 BQ 建議列；供 Portfolio 表與 SSE 失效鍵對齊。
      </p>
      {posLoading && <div className="loading mb-2 text-[13px]">載入建議列…</div>}
      {posError && (
        <div className="error-msg mb-2 text-[13px]">
          無法載入 <code>/api/positions</code>：<code>{posError.message}</code>
        </div>
      )}
      {!posLoading && !posError && openRecs.length === 0 ? (
        <p className="mb-4 text-[13px] text-[var(--muted)]" data-testid="positions-m4-empty">
          目前無 OPEN 建議列。
        </p>
      ) : null}
      {!posLoading && !posError && openRecs.length > 0 ? (
        <div data-testid="positions-m4-table" className="mb-6 overflow-x-auto rounded border border-[color:var(--border)]">
          <table className="w-full min-w-[320px] text-left text-[13px]">
            <thead className="bg-[var(--panel)] text-[11px] uppercase text-[var(--muted)]">
              <tr>
                <th className="px-2 py-2">報告日</th>
                <th className="px-2 py-2">資產</th>
                <th className="px-2 py-2">方向</th>
                <th className="px-2 py-2">狀態</th>
                <th className="px-2 py-2">進場</th>
              </tr>
            </thead>
            <tbody>
              {openRecs.map((r, idx) => (
                <tr key={`${r.asset}-${r.report_date}-${idx}`} className="border-t border-[color:var(--border)]">
                  <td className="px-2 py-2 font-mono text-[12px]">{r.report_date ?? "—"}</td>
                  <td className="px-2 py-2">{r.asset ?? "—"}</td>
                  <td className="px-2 py-2">{r.direction ?? "—"}</td>
                  <td className="px-2 py-2">{r.status ?? "—"}</td>
                  <td className="px-2 py-2">{r.entry_price ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {stats ? (
        <div
          style={{
            display: "flex",
            gap: 16,
            padding: "10px 14px",
            marginBottom: 12,
            background: "var(--panel, rgba(0,0,0,0.03))",
            borderRadius: 8,
            border: "1px solid var(--border)",
            flexWrap: "wrap",
          }}
        >
          <StatsPill label="勝率" value={`${stats.winRate}%`} color={stats.winRate >= 50 ? "var(--green)" : "var(--red)"} />
          <StatsPill label="平均報酬" value={`${stats.avgPnl > 0 ? "+" : ""}${stats.avgPnl}%`} color={Number(stats.avgPnl) >= 0 ? "var(--green)" : "var(--red)"} />
          <StatsPill label="已結算" value={stats.total} />
          <StatsPill label="盈利" value={stats.wins} color="var(--green)" />
        </div>
      ) : null}

      {isLoading && <div className="loading text-[13px]">載入中…</div>}
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
                <th className="px-2 py-2">紙上 P&L</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.signal_id} className="border-t border-[color:var(--border)]">
                  <td className="px-2 py-2 font-mono text-[12px]">{r.signal_id}</td>
                  <td className="px-2 py-2">{r.asset}</td>
                  <td className="px-2 py-2">{r.direction}</td>
                  <td className="px-2 py-2">{statusLabel(r.status)}</td>
                  <td className="px-2 py-2">
                    {isPaperClosedRow(r) ? <PnLArrow row={r} /> : <span style={{ color: "var(--muted)", fontSize: 11 }}>持倉中</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
