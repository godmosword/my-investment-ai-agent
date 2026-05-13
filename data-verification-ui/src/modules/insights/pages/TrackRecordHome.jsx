import { useMemo, useState } from "react";
import Sparkline from "../../../components/Sparkline";
import {
  useTrackRecordByTag,
  useTrackRecordClosed,
  useTrackRecordSummary,
} from "../../../hooks/useApi";

const TAGS = ["AI", "CRYPTO", "WIN", "LOSS"];

function fmtPct(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "0.0%";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function fmtNum(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "0.00";
  return n.toFixed(digits);
}

function tone(value) {
  const n = Number(value);
  if (n > 0) return "text-green-400";
  if (n < 0) return "text-red-400";
  return "text-gray-400";
}

function Kpi({ label, value, sub, valueClass = "text-white", testId }) {
  return (
    <div className="card p-3" data-testid={testId}>
      <div className="metric-label">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${valueClass}`}>{value}</div>
      {sub ? <div className="mt-1 text-[12px] text-[var(--muted)]">{sub}</div> : null}
    </div>
  );
}

function StatusDot({ outcome }) {
  const o = String(outcome ?? "").toLowerCase();
  const cls = o === "win" ? "bg-green-400" : o === "loss" ? "bg-red-400" : "bg-gray-400";
  return <span className={`inline-block h-2 w-2 rounded-full ${cls}`} aria-hidden="true" />;
}

export default function TrackRecordHome() {
  const [tag, setTag] = useState("");
  const summaryQuery = useTrackRecordSummary();
  const closedQuery = useTrackRecordClosed(50, 0);
  const tagQuery = useTrackRecordByTag(tag, 50, 0);

  const payload = tag ? tagQuery.data : closedQuery.data;
  const records = payload?.records ?? [];
  const summary = tag ? payload?.summary : summaryQuery.data;
  const loading = summaryQuery.isLoading || closedQuery.isLoading || (tag && tagQuery.isLoading);
  const error = summaryQuery.error || closedQuery.error || (tag ? tagQuery.error : null);

  const curve = useMemo(() => {
    const values = summary?.equity_curve?.map((point) => Number(point.value));
    return Array.isArray(values) && values.length ? values : [1, 1];
  }, [summary]);

  return (
    <div data-testid="track-record-home" className="px-1">
      <div className="page-header">
        <div className="page-title">Track Record</div>
        <div className="page-subtitle">Paper-only outcomes · source-audited</div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className={`rounded-full border px-3 py-1.5 text-[12px] ${
            !tag ? "border-emerald-400/70 bg-emerald-400/10 text-emerald-100" : "border-white/15 text-white/65"
          }`}
          onClick={() => setTag("")}
        >
          全部
        </button>
        {TAGS.map((row) => (
          <button
            key={row}
            type="button"
            data-testid={`track-record-tag-${row.toLowerCase()}`}
            className={`rounded-full border px-3 py-1.5 text-[12px] ${
              tag === row ? "border-emerald-400/70 bg-emerald-400/10 text-emerald-100" : "border-white/15 text-white/65"
            }`}
            onClick={() => setTag(row)}
          >
            {row}
          </button>
        ))}
      </div>

      {error ? (
        <div className="card mb-3 p-3 text-[13px] text-red-300" role="alert">
          Track Record 暫時無法載入。
        </div>
      ) : null}
      {loading ? <div className="loading mb-3">載入 Track Record…</div> : null}

      <div className="mb-3 grid grid-cols-2 gap-2 lg:grid-cols-6">
        <Kpi
          label="W / L"
          value={`${summary?.wins ?? 0}/${summary?.losses ?? 0}`}
          sub={`${summary?.total_closed ?? 0} closed`}
          testId="track-record-wl"
        />
        <Kpi
          label="Hit Rate"
          value={fmtPct(summary?.hit_rate_pct, 1)}
          valueClass="text-green-400"
          testId="track-record-hit-rate"
        />
        <Kpi
          label="Avg Return"
          value={fmtPct(summary?.avg_return_pct, 2)}
          valueClass={tone(summary?.avg_return_pct)}
        />
        <Kpi label="Sharpe" value={fmtNum(summary?.sharpe, 2)} valueClass="text-cyan-200" />
        <Kpi
          label="Max DD"
          value={fmtPct(summary?.max_drawdown_pct, 1)}
          valueClass="text-red-400"
        />
        <Kpi
          label="Total"
          value={fmtPct(summary?.cumulative_return_pct, 1)}
          valueClass={tone(summary?.cumulative_return_pct)}
        />
      </div>

      <div className="card mb-3 p-3">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <div className="card-title">累積曲線</div>
            <div className="text-[12px] text-[var(--muted)]">{tag ? `${tag} slice` : "all closed signals"}</div>
          </div>
          <div className="font-mono text-[12px] text-[var(--muted)]">{payload?.source ?? summary?.source ?? "—"}</div>
        </div>
        <Sparkline
          values={curve}
          tone={Number(summary?.cumulative_return_pct) >= 0 ? "up" : "down"}
          label="track record equity curve"
        />
      </div>

      <div className="card overflow-hidden p-0">
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--border)] px-3 py-2">
          <div className="card-title">閉倉紀錄</div>
          <div className="text-[12px] text-[var(--muted)]">{records.length} rows</div>
        </div>
        {records.length === 0 && !loading ? (
          <div className="p-3 text-[13px] text-[var(--muted)]">尚無可計算的 closed paper signal。</div>
        ) : (
          <div className="overflow-x-auto">
            <table data-testid="track-record-closed-table" className="w-full min-w-[760px] text-left text-[12px]">
              <thead className="bg-white/[0.03] text-[10px] uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2">Signal</th>
                  <th className="px-3 py-2">Tag</th>
                  <th className="px-3 py-2">Entry</th>
                  <th className="px-3 py-2">Exit</th>
                  <th className="px-3 py-2">Return</th>
                  <th className="px-3 py-2">Closed</th>
                  <th className="px-3 py-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {records.map((row) => (
                  <tr key={row.signal_id} className="border-t border-[color:var(--border)]">
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <StatusDot outcome={row.outcome} />
                        <span className="font-mono text-white/90">{row.asset}</span>
                        <span className={row.direction === "LONG" ? "text-green-400" : "text-red-400"}>
                          {row.direction}
                        </span>
                      </div>
                      <div className="mt-1 max-w-[260px] truncate text-[11px] text-[var(--muted)]">
                        {row.thesis_one_liner || row.signal_id}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-white/70">{row.category || "—"}</td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.entry_price, 2)}</td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.exit_price, 2)}</td>
                    <td className={`px-3 py-2 font-mono font-semibold ${tone(row.return_pct)}`}>
                      {fmtPct(row.return_pct, 2)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]">
                      {String(row.closed_at ?? "").slice(0, 10) || "—"}
                    </td>
                    <td className="px-3 py-2">
                      <code className="rounded bg-white/5 px-1.5 py-0.5 text-[11px] text-cyan-200">
                        {row.source_id}
                      </code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
