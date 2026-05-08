import { useExecutionIntents } from "../../../hooks/useApi";

function paperEntry(r) {
  return r.paper_fill_price ?? r.paper_entry ?? r.reference_entry_price ?? r.entry_price ?? null;
}

function paperExit(r) {
  return r.paper_exit_price ?? r.paper_exit ?? null;
}

/** Rows counted as closed for paper PnL stats (API + legacy aliases). */
function isPaperClosedRow(r) {
  const s = String(r.status ?? "").toUpperCase();
  return s === "PAPER_CLOSED" || s === "CLOSED" || s === "EXITED";
}

function calcStats(rows) {
  if (!rows || rows.length === 0) return null;
  const closed = rows.filter(isPaperClosedRow);
  if (closed.length === 0) return null;

  const wins = closed.filter((r) => {
    const px = paperExit(r);
    const en = paperEntry(r);
    if (px == null || en == null) return false;
    const dir = (r.direction ?? "").toUpperCase();
    return dir === "LONG" ? px > en : px < en;
  });

  const winRate = closed.length > 0 ? Math.round((wins.length / closed.length) * 100) : 0;

  const pnls = closed
    .map((r) => {
      const px = paperExit(r);
      const en = paperEntry(r);
      if (px == null || en == null) return null;
      const dir = (r.direction ?? "").toUpperCase();
      const raw =
        dir === "LONG" ? (px - en) / en : (en - px) / en;
      return raw * 100;
    })
    .filter((v) => v != null);

  const avgPnl = pnls.length > 0 ? pnls.reduce((a, b) => a + b, 0) / pnls.length : 0;

  const winPnls = pnls.filter((v) => v > 0);
  const losePnls = pnls.filter((v) => v < 0);
  const avgWin = winPnls.length ? winPnls.reduce((a, b) => a + b, 0) / winPnls.length : 0;
  const avgLoss = losePnls.length ? Math.abs(losePnls.reduce((a, b) => a + b, 0) / losePnls.length) : 1;
  const rr = avgLoss > 0 ? (avgWin / avgLoss).toFixed(2) : "—";

  return { total: closed.length, wins: wins.length, winRate, avgPnl: avgPnl.toFixed(2), rr };
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div className="card" style={{ textAlign: "center" }}>
      <div className="metric-label">{label}</div>
      <div
        className="metric-value"
        style={{ color: color ?? "var(--text)", fontSize: 28, marginTop: 4 }}
      >
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    PENDING_REVIEW: { label: "待審", color: "var(--muted)" },
    APPROVED_FOR_PAPER: { label: "紙上運行", color: "var(--accent)" },
    REJECTED: { label: "已駁回", color: "var(--red)" },
    PAPER_SUBMITTED: { label: "紙上提交", color: "var(--accent)" },
    PAPER_FILLED: { label: "紙上成交", color: "var(--green)" },
    PAPER_CLOSED: { label: "紙上結算", color: "var(--muted)" },
    EXITED: { label: "已出場", color: "var(--yellow)" },
    CLOSED: { label: "已關閉", color: "var(--muted)" },
    SUPERSEDED: { label: "已取代", color: "var(--muted)" },
  };
  const info = map[status] ?? { label: status ?? "—", color: "var(--muted)" };
  return (
    <span
      style={{
        fontSize: 10,
        padding: "2px 7px",
        borderRadius: 4,
        background: `${info.color}22`,
        color: info.color,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {info.label}
    </span>
  );
}

function isActiveIntent(r) {
  const s = String(r.status ?? "").toUpperCase();
  if (s === "REJECTED" || s === "SUPERSEDED") return false;
  if (isPaperClosedRow(r)) return false;
  return true;
}

export default function QuantHome() {
  const { data: rows = [], isLoading, error } = useExecutionIntents(200, {
    livePoll: false,
    statusFilter: "all",
    categoryFilter: "all",
    sortBy: "updated_desc",
  });

  const stats = calcStats(rows);
  const active = rows.filter(isActiveIntent);

  return (
    <div className="page-content" style={{ padding: "16px 16px 80px" }}>
      <div className="page-header">
        <div className="page-title">量化交易</div>
        <div className="page-subtitle">紙上模擬績效（execution_intents · 僅追蹤，不下單）</div>
      </div>

      {isLoading && <div className="loading" style={{ padding: "20px 0" }}>載入中…</div>}
      {error && (
        <div className="error-msg">
          無法載入意圖紀錄：<code>{error.message}</code>
        </div>
      )}

      {/* KPI grid */}
      {stats ? (
        <>
          <div className="section-header subtle">績效概覽（已結算信號）</div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
              gap: 10,
              marginBottom: 16,
            }}
          >
            <KpiCard label="勝率" value={`${stats.winRate}%`} sub={`${stats.wins}/${stats.total}`} color="var(--green)" />
            <KpiCard label="平均盈虧" value={`${stats.avgPnl}%`} color={Number(stats.avgPnl) >= 0 ? "var(--green)" : "var(--red)"} />
            <KpiCard label="盈虧比 R:R" value={stats.rr} sub="avg win / avg loss" color="var(--accent)" />
            <KpiCard label="總信號數" value={stats.total} color="var(--text)" />
          </div>
        </>
      ) : !isLoading && !error ? (
        <div className="card" style={{ marginBottom: 12, color: "var(--muted)", fontSize: 13 }}>
          尚無已結算信號可計算績效。
        </div>
      ) : null}

      {/* Active signals */}
      <div className="section-header subtle">運行中信號（{active.length}）</div>
      {active.length === 0 && !isLoading && (
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>目前無運行中信號。</div>
      )}
      {active.slice(0, 20).map((r) => (
        <div key={r.signal_id} className="card" style={{ marginBottom: 8, padding: "12px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div>
              <span style={{ fontWeight: 700, fontSize: 15 }}>{r.asset ?? "—"}</span>
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  fontWeight: 600,
                  color:
                    (r.direction ?? "").toUpperCase() === "LONG"
                      ? "var(--green)"
                      : "var(--red)",
                }}
              >
                {r.direction ?? "—"}
              </span>
            </div>
            <StatusPill status={r.status} />
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 8,
              fontSize: 12,
            }}
          >
            {[
              { l: "進場", v: paperEntry(r) },
              { l: "出場", v: paperExit(r) ?? "—" },
              { l: "類別", v: r.category ?? "—" },
            ].map(({ l, v }) => (
              <div key={l}>
                <div style={{ color: "var(--muted)", fontSize: 10, marginBottom: 2 }}>{l}</div>
                <div style={{ fontWeight: 600 }}>{v ?? "—"}</div>
              </div>
            ))}
          </div>
          {(r.thesis_one_liner || r.thesis) && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 8, lineHeight: 1.45 }}>
              {r.thesis_one_liner ?? r.thesis}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
