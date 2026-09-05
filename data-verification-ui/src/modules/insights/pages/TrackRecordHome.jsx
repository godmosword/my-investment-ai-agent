import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import {
  useTrackRecordByTag,
  useTrackRecordClosed,
  useTrackRecordSummary,
} from "../../../hooks/useApi";
import { insightsSymbolHref } from "../../../constants/portalPhase4";

const EquityCurveChart = lazy(() => import("../../../components/charts/EquityCurveChart"));

const TAGS = ["AI", "CRYPTO", "WIN", "LOSS"];

function fmtPct(value, digits = 1) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function fmtNum(value, digits = 2) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  return n.toFixed(digits);
}

function presentCount(value) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  return n;
}

function wlLabel(summary) {
  if (!summary || typeof summary !== "object") return "UNKNOWN／未提供";
  return `${presentCount(summary.wins)}/${presentCount(summary.losses)}`;
}

function presentCategory(value) {
  const s = String(value ?? "").trim();
  return s || "UNKNOWN";
}

function presentClosedAt(value) {
  const s = String(value ?? "").trim();
  if (!s) return "UNKNOWN";
  const prefix = s.slice(0, 10).trim();
  return prefix || "UNKNOWN";
}

function presentSource(value) {
  const s = String(value ?? "").trim();
  return s || "UNKNOWN";
}

function presentDateStamp(value) {
  const s = String(value ?? "").trim();
  if (!s) return "UNKNOWN";
  const prefix = s.slice(0, 10).trim();
  return prefix || "UNKNOWN";
}

function presentPeriod(start, end) {
  const a = presentDateStamp(start);
  const b = presentDateStamp(end);
  if (a === "UNKNOWN" && b === "UNKNOWN") return "UNKNOWN";
  if (a === "UNKNOWN") return b;
  if (b === "UNKNOWN") return a;
  return a === b ? a : `${a} – ${b}`;
}

function presentSampleSize(summary) {
  if (!summary || typeof summary !== "object") return "UNKNOWN";
  for (const key of ["sample_size", "total_closed", "source_row_count"]) {
    if (summary[key] == null || summary[key] === "") continue;
    const n = Number(summary[key]);
    if (Number.isFinite(n)) return n;
  }
  return "UNKNOWN";
}

function payloadAppliesQuality(summary) {
  if (!summary || typeof summary !== "object") return false;
  if (summary.quality != null && summary.quality !== "") return true;
  if (summary.quality_adjusted != null && summary.quality_adjusted !== "") return true;
  if (summary.avg_quality_score != null && summary.avg_quality_score !== "") return true;
  const rules = summary.inclusion_rules;
  if (rules && typeof rules === "object") {
    if (rules.quality_weighted === true || rules.quality_filter_applied === true) return true;
  }
  return false;
}

function presentPriorAlignment(value) {
  if (value == null || value === "") return "UNKNOWN";
  if (typeof value !== "object") return "UNKNOWN";
  if (value.available === false) return "UNKNOWN";
  const parts = [];
  if (value.evidence_field) parts.push(`證據欄 ${value.evidence_field}`);
  if (value.linked_count != null && Number.isFinite(Number(value.linked_count))) {
    parts.push(`帶上期連結 ${Number(value.linked_count)}`);
  }
  if (value.aligned_count != null && Number.isFinite(Number(value.aligned_count))) {
    parts.push(`標記對齊 ${Number(value.aligned_count)}`);
  }
  if (value.sample_size != null && Number.isFinite(Number(value.sample_size))) {
    parts.push(`樣本 ${Number(value.sample_size)}`);
  }
  if (value.match_rate_pct != null && Number.isFinite(Number(value.match_rate_pct))) {
    parts.push(`對齊率 ${Number(value.match_rate_pct)}%`);
  }
  return parts.length ? parts.join(" · ") : "UNKNOWN";
}

function AuditMeta({ summary, source, testIdPrefix }) {
  return (
    <div
      className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[12px] text-[var(--muted)]"
      data-testid={`${testIdPrefix}-audit-meta`}
    >
      <span data-testid={`${testIdPrefix}-audit-period`}>期間 {presentPeriod(summary?.period_start, summary?.period_end)}</span>
      <span data-testid={`${testIdPrefix}-audit-as-of`}>截至 {presentDateStamp(summary?.as_of)}</span>
      <span data-testid={`${testIdPrefix}-audit-sample`}>樣本 {presentSampleSize(summary)}</span>
      <span data-testid={`${testIdPrefix}-audit-source`}>來源 {presentSource(source)}</span>
    </div>
  );
}

function InclusionPanel({ summary }) {
  const rules = summary?.inclusion_rules && typeof summary.inclusion_rules === "object" ? summary.inclusion_rules : null;
  const notes = Array.isArray(rules?.notes) ? rules.notes.filter((row) => String(row || "").trim()) : [];
  const statuses = Array.isArray(rules?.included_statuses) ? rules.included_statuses : [];
  const required = Array.isArray(rules?.required_fields) ? rules.required_fields : [];
  const qualityNote = payloadAppliesQuality(summary) ? null : "本頁未套用 quality 權重";

  return (
    <details
      className="card mb-3 p-3 text-[13px] leading-relaxed text-white/78"
      data-testid="track-record-inclusion-panel"
      open
    >
      <summary
        className="cursor-pointer font-semibold text-cyan-100"
        data-testid="track-record-inclusion-summary"
      >
        內部透明度／納入規則
      </summary>
      <div className="mt-2 space-y-2 text-white/70">
        {rules?.universe ? (
          <div data-testid="track-record-inclusion-universe">
            宇宙 <code className="font-mono text-cyan-200">{rules.universe}</code>
          </div>
        ) : (
          <div data-testid="track-record-inclusion-universe">宇宙 paper-tracked 已結紙上結果</div>
        )}
        {statuses.length ? (
          <div data-testid="track-record-inclusion-included">
            納入{" "}
            {statuses.map((row) => (
              <code key={row} className="mr-1 font-mono text-cyan-200">
                {row}
              </code>
            ))}
          </div>
        ) : rules ? null : (
          <div data-testid="track-record-inclusion-included">
            納入 已結紙上意圖（PAPER_CLOSED／CLOSED／EXITED），且具備訊號、標的、方向、進場／出場價與可計算報酬。
          </div>
        )}
        {rules ? null : (
          <div data-testid="track-record-inclusion-excluded">
            排除 未結、被拒、被取代、待審，或缺價／缺報酬列。
          </div>
        )}
        {required.length ? (
          <div data-testid="track-record-inclusion-required">
            必要欄位 {required.join("、")}
          </div>
        ) : null}
        {notes
          .filter((note) => !String(note).includes("本頁未套用 quality 權重"))
          .map((note) => (
            <div key={note}>{note}</div>
          ))}
        {qualityNote ? (
          <div className="text-amber-100/90" data-testid="track-record-quality-note">
            {qualityNote}
          </div>
        ) : null}
        <div data-testid="track-record-prior-alignment">
          上期建議追蹤 {presentPriorAlignment(summary?.prior_alignment)}
        </div>
      </div>
    </details>
  );
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
  const summaryPresent = summary != null && typeof summary === "object";
  const loading = summaryQuery.isLoading || closedQuery.isLoading || (tag && tagQuery.isLoading);
  const error = summaryQuery.error || closedQuery.error || (tag ? tagQuery.error : null);
  const emptyAll = !tag && !loading && !error && summaryPresent && Number(summary.total_closed) === 0;

  return (
    <div data-testid="track-record-home" className="px-1">
      <div className="page-header">
        <div className="page-title">實績</div>
        <div className="page-subtitle">僅紙上結果 · 來源可稽核</div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          className={`min-h-[36px] rounded-full border px-3 py-1.5 text-[12px] ${
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
            className={`min-h-[36px] rounded-full border px-3 py-1.5 text-[12px] ${
              tag === row ? "border-emerald-400/70 bg-emerald-400/10 text-emerald-100" : "border-white/15 text-white/65"
            }`}
            onClick={() => setTag(row)}
          >
            {row}
          </button>
        ))}
      </div>

      {error ? (
        <div className="card mb-3 p-3 text-[13px] text-red-300" data-testid="track-record-error" role="alert">
          實績暫時無法載入。
        </div>
      ) : null}
      {loading && !summaryPresent ? (
        <div className="loading mb-3" data-testid="track-record-loading" role="status">
          載入實績…
        </div>
      ) : null}
      {!loading && !error && !summaryPresent ? (
        <div
          className="card mb-3 p-3 text-[13px] text-[var(--muted)]"
          data-testid="track-record-unknown-empty"
          role="status"
        >
          UNKNOWN：尚無實績摘要
        </div>
      ) : null}

      {emptyAll ? (
        <div
          data-testid="track-record-empty-guidance"
          className="card mb-3 border border-cyan-300/20 bg-cyan-950/[0.08] p-3 text-[13px] leading-relaxed text-white/78"
        >
          <div className="font-semibold text-cyan-100">還缺已結紙上訊號</div>
          <p className="mt-1 mb-0 text-white/65">
            實績需要已關閉的紙上意圖，或 <code className="font-mono">recommendation_outcomes</code>{" "}
            的市價結算列。先在「紙上生命週期」建立／推進紙上意圖，或排程{" "}
            <code className="font-mono">scripts/mark_recommendations.py</code> 後再讀績效。
          </p>
        </div>
      ) : null}

      {summaryPresent ? (
      <div className="mb-3 grid grid-cols-2 gap-2 lg:grid-cols-6">
        <Kpi
          label="勝／負"
          value={wlLabel(summary)}
          sub={`${presentCount(summary?.total_closed)} 已結`}
          testId="track-record-wl"
        />
        <Kpi
          label="命中率"
          value={fmtPct(summary?.hit_rate_pct, 1)}
          valueClass="text-green-400"
          testId="track-record-hit-rate"
        />
        <Kpi
          label="平均報酬"
          value={fmtPct(summary?.avg_return_pct, 2)}
          valueClass={tone(summary?.avg_return_pct)}
          testId="track-record-avg-return"
        />
        <Kpi
          label={
            <span title="夏普比率" aria-label="夏普比率">
              Sharpe
              <span className="ml-1 text-[10px] font-normal normal-case text-[var(--muted)]">夏普</span>
            </span>
          }
          value={fmtNum(summary?.sharpe, 2)}
          valueClass="text-cyan-200"
          testId="track-record-sharpe"
        />
        <Kpi
          label="最大回撤"
          value={fmtPct(summary?.max_drawdown_pct, 1)}
          valueClass="text-red-400"
          testId="track-record-max-dd"
        />
        <Kpi
          label="累積"
          value={fmtPct(summary?.cumulative_return_pct, 1)}
          valueClass={tone(summary?.cumulative_return_pct)}
          testId="track-record-cumulative"
        />
      </div>
      ) : null}

      {summaryPresent ? (
        <div className="mb-3">
          <AuditMeta
            summary={summary}
            source={payload?.source ?? summary?.source}
            testIdPrefix="track-record"
          />
        </div>
      ) : null}

      {summaryPresent ? <InclusionPanel summary={summary} /> : null}

      {summaryPresent ? (
      <div className="card mb-3 p-3" data-testid="track-record-equity-card">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <div className="card-title">累積曲線</div>
            <div className="text-[12px] text-[var(--muted)]" data-testid="track-record-equity-subtitle">
              {tag ? `${tag} 篩選` : "全部已結"}
            </div>
          </div>
          <div className="font-mono text-[12px] text-[var(--muted)]" data-testid="track-record-equity-source">
            {presentSource(payload?.source ?? summary?.source)}
          </div>
        </div>
        <div className="mb-2">
          <AuditMeta
            summary={summary}
            source={payload?.source ?? summary?.source}
            testIdPrefix="track-record-equity"
          />
        </div>
        <Suspense fallback={<div className="loading text-[12px] text-white/50">載入曲線…</div>}>
          <EquityCurveChart curve={summary?.equity_curve || []} />
        </Suspense>
      </div>
      ) : null}

      {summaryPresent ? (
      <div className="card overflow-hidden p-0" data-testid="track-record-closed-card">
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--border)] px-3 py-2">
          <div className="card-title">閉倉紀錄</div>
          <div className="text-[12px] text-[var(--muted)]" data-testid="track-record-closed-count">
            {records.length} 筆
          </div>
        </div>
        {records.length === 0 && !loading ? (
          <div className="p-3 text-[13px] text-[var(--muted)]">尚無可計算的已結紙上訊號。</div>
        ) : (
          <div className="overflow-x-auto">
            <table data-testid="track-record-closed-table" className="w-full min-w-[760px] text-left text-[12px]">
              <thead className="bg-white/[0.03] text-[10px] uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2">訊號</th>
                  <th className="px-3 py-2">標籤</th>
                  <th className="px-3 py-2">進場</th>
                  <th className="px-3 py-2">出場</th>
                  <th className="px-3 py-2">報酬</th>
                  <th className="px-3 py-2">結案</th>
                  <th className="px-3 py-2">來源</th>
                  <th className="px-3 py-2">操作</th>
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
                    <td className="px-3 py-2 text-white/70" data-testid="track-record-row-category">
                      {presentCategory(row.category)}
                    </td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.entry_price, 2)}</td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.exit_price, 2)}</td>
                    <td className={`px-3 py-2 font-mono font-semibold ${tone(row.return_pct)}`}>
                      {fmtPct(row.return_pct, 2)}
                    </td>
                    <td
                      className="px-3 py-2 font-mono text-[11px] text-[var(--muted)]"
                      data-testid="track-record-row-closed-at"
                    >
                      {presentClosedAt(row.closed_at)}
                    </td>
                    <td className="px-3 py-2">
                      <code className="rounded bg-white/5 px-1.5 py-0.5 text-[11px] text-cyan-200">
                        {row.source_id}
                      </code>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        {String(row.asset ?? "").trim() ? (
                          <Link
                            to={insightsSymbolHref(row.asset)}
                            data-testid="track-record-action-deep-dive"
                            className="inline-flex min-h-[36px] items-center rounded border border-emerald-500/30 px-2 py-1 text-[11px] text-emerald-100/90 hover:bg-emerald-950/20"
                          >
                            深入
                          </Link>
                        ) : null}
                        {String(row.asset ?? "").trim() ? (
                          <Link
                            to={`/portfolio?tab=monitor&focus=${encodeURIComponent(String(row.asset).trim().toUpperCase())}`}
                            data-testid="track-record-action-monitor"
                            className="inline-flex min-h-[36px] items-center rounded border border-white/15 px-2 py-1 text-[11px] text-white/75 hover:bg-white/5"
                          >
                            監控
                          </Link>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      ) : null}
    </div>
  );
}
