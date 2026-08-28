import { useMemo, useState } from "react";
import ExecutionIntentsBlotter from "../../../components/ExecutionIntentsBlotter";
import {
  useCreateExecutionIntent,
  usePaperLifecycle,
  usePaperPnl,
  usePaperTransparencyLetter,
} from "../../../hooks/useApi";

const INITIAL_FORM = {
  category: "AI",
  asset: "",
  direction: "LONG",
  star_rating: 1,
  thesis_one_liner: "",
  reference_entry_price: "",
  reference_target_price: "",
  reference_stop_price: "",
};

function fmtPct(value) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function fmtNum(value) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function presentCount(value) {
  if (value == null || value === "") return "UNKNOWN／未提供";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNKNOWN／未提供";
  return n;
}

function presentWinsLosses(summary) {
  const winsMissing = summary?.wins == null || summary?.wins === "";
  const lossesMissing = summary?.losses == null || summary?.losses === "";
  if (winsMissing && lossesMissing) return "UNKNOWN／未提供";
  const wins = winsMissing ? "UNKNOWN／未提供" : presentCount(summary.wins);
  const losses = lossesMissing ? "UNKNOWN／未提供" : presentCount(summary.losses);
  return `${wins} wins / ${losses} losses`;
}

function sampleLabel(summary) {
  if (summary?.publishable) return "sample ready";
  const closed = presentCount(summary?.closed_count);
  const min = presentCount(summary?.min_publishable_sample);
  return `sample ${closed}/${min}`;
}

function colorFor(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "text-white/70";
  return n > 0 ? "text-emerald-300" : "text-red-300";
}

function qualityTone(grade) {
  if (grade === "A") return "border-emerald-300/40 bg-emerald-400/10 text-emerald-200";
  if (grade === "B") return "border-cyan-300/40 bg-cyan-400/10 text-cyan-200";
  if (grade === "C") return "border-amber-300/40 bg-amber-400/10 text-amber-200";
  if (grade === "D") return "border-red-300/40 bg-red-400/10 text-red-200";
  return "border-white/10 bg-white/[0.03] text-white/55";
}

function QualityBadge({ row }) {
  const grade = String(row?.quality_grade ?? "").trim();
  const score = Number(row?.quality_score);
  return (
    <span
      data-testid="paper-quality-badge"
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[11px] font-semibold ${qualityTone(grade)}`}
      title={(row?.quality_reasons || []).join(", ")}
    >
      {grade || "UNKNOWN／未提供"}
      <span className="text-white/55">{Number.isFinite(score) ? score : "UNKNOWN／未提供"}</span>
    </span>
  );
}

function Kpi({ label, value, sub, testId, tone }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] p-3" data-testid={testId}>
      <div className="text-[11px] uppercase text-[var(--muted)]">{label}</div>
      <div className={`mt-1 text-[24px] font-semibold ${tone || "text-white"}`}>{value}</div>
      {sub ? <div className="mt-1 text-[11px] text-[var(--muted)]">{sub}</div> : null}
    </div>
  );
}

function IntentCreateForm() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(INITIAL_FORM);
  const mutation = useCreateExecutionIntent();

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: key === "asset" ? value.toUpperCase() : value }));
  };

  const submit = (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      star_rating: Number(form.star_rating) || 1,
      reference_entry_price: form.reference_entry_price === "" ? null : Number(form.reference_entry_price),
      reference_target_price: form.reference_target_price === "" ? null : Number(form.reference_target_price),
      reference_stop_price: form.reference_stop_price === "" ? null : Number(form.reference_stop_price),
    };
    mutation.mutate(payload, {
      onSuccess: () => {
        setForm(INITIAL_FORM);
        setOpen(false);
      },
    });
  };

  return (
    <div className="rounded border border-white/10 bg-white/[0.03] p-3" data-testid="paper-intent-create">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[14px] font-semibold text-white">手動建立意圖</div>
          <div className="text-[12px] text-[var(--muted)]">建立 PENDING_REVIEW row；不下單。</div>
        </div>
        <button
          type="button"
          data-testid="paper-intent-create-toggle"
          className="min-h-[40px] rounded border border-emerald-400/40 px-3 py-1.5 text-[13px] font-semibold text-emerald-100 hover:bg-emerald-400/10"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收合" : "+ 新增意圖"}
        </button>
      </div>
      {open ? (
        <form className="mt-3 grid gap-2 md:grid-cols-6" onSubmit={submit}>
          <label className="text-[12px] text-white/70">
            Category
            <select
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.category}
              onChange={(e) => setField("category", e.target.value)}
            >
              <option value="AI">AI</option>
              <option value="CRYPTO">CRYPTO</option>
            </select>
          </label>
          <label className="text-[12px] text-white/70">
            Symbol
            <input
              required
              data-testid="paper-intent-asset"
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 font-mono text-white"
              value={form.asset}
              onChange={(e) => setField("asset", e.target.value)}
              placeholder="NVDA"
            />
          </label>
          <label className="text-[12px] text-white/70">
            Direction
            <select
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.direction}
              onChange={(e) => setField("direction", e.target.value)}
            >
              <option value="LONG">LONG</option>
              <option value="SHORT">SHORT</option>
            </select>
          </label>
          <label className="text-[12px] text-white/70">
            Entry
            <input
              type="number"
              step="any"
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.reference_entry_price}
              onChange={(e) => setField("reference_entry_price", e.target.value)}
            />
          </label>
          <label className="text-[12px] text-white/70">
            Target
            <input
              type="number"
              step="any"
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.reference_target_price}
              onChange={(e) => setField("reference_target_price", e.target.value)}
            />
          </label>
          <label className="text-[12px] text-white/70">
            Stop
            <input
              type="number"
              step="any"
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.reference_stop_price}
              onChange={(e) => setField("reference_stop_price", e.target.value)}
            />
          </label>
          <label className="md:col-span-5 text-[12px] text-white/70">
            Thesis
            <input
              className="mt-1 w-full rounded border border-white/15 bg-black/40 px-2 py-2 text-white"
              value={form.thesis_one_liner}
              onChange={(e) => setField("thesis_one_liner", e.target.value)}
              placeholder="One-line thesis"
            />
          </label>
          <button
            type="submit"
            data-testid="paper-intent-create-submit"
            disabled={mutation.isPending}
            className="min-h-[42px] self-end rounded bg-emerald-700/80 px-3 py-2 text-[13px] font-semibold text-white disabled:opacity-50"
          >
            {mutation.isPending ? "建立中…" : "建立"}
          </button>
          {mutation.isError ? (
            <div className="md:col-span-6 text-[12px] text-red-300" role="alert">
              建立失敗：{mutation.error?.message}
            </div>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}

function LifecycleTable({ rows }) {
  const visible = Array.isArray(rows) ? rows.slice(0, 30) : [];
  if (visible.length === 0) {
    return <div className="rounded border border-white/10 p-3 text-[13px] text-[var(--muted)]">目前沒有紙上生命週期 rows。</div>;
  }
  return (
    <div className="overflow-x-auto rounded border border-white/10" data-testid="paper-lifecycle-table">
      <table className="w-full min-w-[760px] text-left text-[12px]">
        <thead className="bg-white/[0.04] uppercase text-[var(--muted)]">
          <tr>
            <th className="px-2 py-2">Signal</th>
            <th className="px-2 py-2">Status</th>
            <th className="px-2 py-2">Quality</th>
            <th className="px-2 py-2">Entry / Mark</th>
            <th className="px-2 py-2">P&L</th>
            <th className="px-2 py-2">Risk</th>
            <th className="px-2 py-2">Thesis</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={row.signal_id} className="border-t border-white/10">
              <td className="px-2 py-2">
                <div className="font-mono text-white">{row.asset}</div>
                <div className="font-mono text-[10px] text-[var(--muted)]">{row.signal_id}</div>
                <div className="text-[11px] text-white/60">{row.direction} · {row.category || "—"}</div>
              </td>
              <td className="px-2 py-2 text-white/75">{row.status}</td>
              <td className="px-2 py-2">
                <QualityBadge row={row} />
                {Array.isArray(row.quality_reasons) && row.quality_reasons.length ? (
                  <div className="mt-1 max-w-[150px] truncate text-[10px] text-[var(--muted)]">
                    {row.quality_reasons.slice(0, 3).join(" · ")}
                  </div>
                ) : null}
              </td>
              <td className="px-2 py-2 font-mono text-white/75">
                {fmtNum(row.entry_price)} / {fmtNum(row.mark_price)}
                {row.quote_error ? <div className="text-[11px] text-red-300">quote unavailable</div> : null}
              </td>
              <td className={`px-2 py-2 font-semibold ${colorFor(row.return_pct)}`}>{fmtPct(row.return_pct)}</td>
              <td className="px-2 py-2 text-white/70">
                <div>R {fmtNum(row.r_multiple)}</div>
                <div className="text-[11px] text-[var(--muted)]">
                  tgt {fmtPct(row.target_distance_pct)} / stop {fmtPct(row.stop_distance_pct)}
                </div>
              </td>
              <td className="px-2 py-2 text-white/65">{row.thesis_one_liner || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TransparencyLetterCard({ letter }) {
  const summary = letter.data?.summary || {};
  const alignment = letter.data?.alignment || {};
  const matched = alignment.matched_symbols || [];
  const paperOnly = alignment.paper_only_symbols || [];
  const portfolioOnly = alignment.portfolio_only_symbols || [];

  return (
    <section className="rounded border border-white/10 bg-white/[0.03] p-3" data-testid="paper-transparency-letter">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[12px] font-semibold uppercase text-cyan-200">Monthly Transparency Letter</div>
          <div data-testid="paper-letter-month" className="mt-1 text-[18px] font-semibold text-white">{letter.data?.month || "UNKNOWN"}</div>
          <div className="mt-1 text-[12px] text-[var(--muted)]">
            Internal-only paper letter · publishable only after minimum sample and human review.
          </div>
        </div>
        <span
          className={`rounded border px-2 py-1 text-[12px] ${
            summary.publishable
              ? "border-emerald-300/40 bg-emerald-400/10 text-emerald-200"
              : "border-amber-300/40 bg-amber-400/10 text-amber-200"
          }`}
          data-testid="paper-letter-publishable"
        >
          {sampleLabel(summary)}
        </span>
      </div>

      {letter.isLoading ? (
        <div className="mt-3 text-[13px] text-[var(--muted)]">生成透明月報…</div>
      ) : letter.error ? (
        <div className="mt-3 text-[13px] text-red-300" role="alert">透明月報暫時無法載入：{letter.error.message}</div>
      ) : (
        <div className="mt-3 grid gap-2 lg:grid-cols-[1fr_1.3fr]">
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <Kpi label="Closed" value={presentCount(summary.closed_count)} sub={presentWinsLosses(summary)} />
            <Kpi label="Avg Return" value={fmtPct(summary.avg_return_pct)} tone={colorFor(summary.avg_return_pct)} />
            <Kpi label="Win Rate" value={fmtPct(summary.win_rate_pct)} />
            <Kpi label="Avg Quality" value={fmtNum(summary.avg_quality_score)} />
          </div>
          <div className="rounded border border-white/10 bg-black/20 p-3">
            <div className="text-[12px] font-semibold uppercase text-white/70">Portfolio Alignment</div>
            <div className="mt-2 flex flex-wrap gap-2 text-[12px]">
              <span className="rounded border border-emerald-300/30 px-2 py-1 text-emerald-200">
                matched {matched.join(", ") || "none"}
              </span>
              <span className="rounded border border-cyan-300/30 px-2 py-1 text-cyan-200">
                paper-only {paperOnly.join(", ") || "none"}
              </span>
              <span className="rounded border border-white/15 px-2 py-1 text-white/65">
                portfolio-only {portfolioOnly.join(", ") || "none"}
              </span>
            </div>
            <pre className="mt-3 max-h-32 overflow-auto whitespace-pre-wrap rounded border border-white/10 bg-black/30 p-2 text-[11px] text-white/65">
              {letter.data?.letter_markdown || ""}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}

export default function PaperLifecycleHome() {
  const lifecycle = usePaperLifecycle();
  const pnl = usePaperPnl();
  const letter = usePaperTransparencyLetter();
  const summarySource = pnl.data?.summary || lifecycle.data?.summary || null;
  const summary = summarySource && typeof summarySource === "object" ? summarySource : {};
  const rows = useMemo(() => pnl.data?.rows || lifecycle.data?.rows || [], [pnl.data, lifecycle.data]);
  const summaryLoading = (lifecycle.isLoading || pnl.isLoading) && !summarySource;
  const summaryError = Boolean(lifecycle.error || pnl.error) && !summarySource;

  return (
    <div data-testid="paper-lifecycle-home" className="space-y-3">
      <div className="page-header">
        <div className="page-title">紙上生命週期</div>
        <div className="page-subtitle">execution_intents.jsonl · paper P&L · risk metrics · 不下單</div>
      </div>

      {(lifecycle.error || pnl.error) ? (
        <div
          className="rounded border border-red-400/30 bg-red-500/10 p-3 text-[13px] text-red-200"
          data-testid="paper-lifecycle-error"
          role="alert"
        >
          紙上資料暫時無法載入：{pnl.error?.message || lifecycle.error?.message}
        </div>
      ) : null}

      {summaryLoading ? (
        <div
          className="rounded border border-white/10 p-3 text-[13px] text-[var(--muted)]"
          data-testid="paper-lifecycle-loading"
          role="status"
        >
          載入紙上生命週期…
        </div>
      ) : summaryError ? null : !summarySource ? (
        <div
          className="rounded border border-white/10 p-3 text-[13px] text-[var(--muted)]"
          data-testid="paper-lifecycle-empty"
          role="status"
        >
          UNKNOWN：尚無紙上生命週期摘要
        </div>
      ) : (
      <div className="grid gap-2 md:grid-cols-4">
        <Kpi label="Active" value={presentCount(summary.active_count)} sub="approved/submitted/filled" testId="paper-kpi-active" />
        <Kpi label="Closed" value={presentCount(summary.closed_count)} sub={presentWinsLosses(summary)} testId="paper-kpi-closed" />
        <Kpi label="Realized" value={fmtPct(summary.avg_realized_return_pct)} tone={colorFor(summary.avg_realized_return_pct)} testId="paper-kpi-realized" />
        <Kpi
          label="Quality"
          value={fmtNum(summary.avg_quality_score)}
          sub={summary.quality_counts ? `A ${presentCount(summary.quality_counts.A)} · B ${presentCount(summary.quality_counts.B)}` : "UNKNOWN／未提供"}
          testId="paper-kpi-quality"
        />
      </div>
      )}

      {summary.avg_return_by_quality && Object.keys(summary.avg_return_by_quality).length ? (
        <div className="rounded border border-white/10 bg-white/[0.03] p-3" data-testid="paper-quality-vs-pnl">
          <div className="mb-2 text-[12px] font-semibold uppercase text-cyan-200">Quality vs P&L</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.avg_return_by_quality).map(([grade, value]) => (
              <span key={grade} className={`rounded border px-2 py-1 text-[12px] ${qualityTone(grade)}`}>
                {grade}: {fmtPct(value)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <IntentCreateForm />
      <TransparencyLetterCard letter={letter} />

      {lifecycle.isLoading || pnl.isLoading ? (
        <div className="rounded border border-white/10 p-3 text-[13px] text-[var(--muted)]">載入紙上生命週期…</div>
      ) : (
        <LifecycleTable rows={rows} />
      )}

      <ExecutionIntentsBlotter />
    </div>
  );
}
