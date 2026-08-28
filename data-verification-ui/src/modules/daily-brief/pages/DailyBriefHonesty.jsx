import { Link } from "react-router-dom";
import { useReports, useReport, useStructuredReport } from "../../../hooks/useApi";

function reportsList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.reports)) return data.reports;
  return [];
}

function aiInterpretation(value) {
  const text = String(value ?? "").trim();
  return text || "UNKNOWN／未提供";
}

function firstTake(report) {
  if (!report || typeof report !== "object") return "";
  return report.gemini_take || report.grok_summary || report.gpt_summary || "";
}

function cryptoBrief(structured) {
  const brief = structured?.daily_brief_report?.crypto;
  return brief && typeof brief === "object" ? brief : {};
}

export default function DailyBriefHonesty() {
  const reports = useReports(5);
  const rows = reportsList(reports.data);
  const latestDate = rows[0]?.report_date ? String(rows[0].report_date) : "";
  const detail = useReport(latestDate, { enabled: Boolean(latestDate) });
  const structured = useStructuredReport(latestDate, "full", { enabled: Boolean(latestDate) });

  if (reports.isLoading || (latestDate && (detail.isLoading || structured.isLoading))) {
    return (
      <div data-testid="daily-brief-loading" className="card mb-3 p-4 text-[13px] text-white/70" role="status">
        載入今日建議…
      </div>
    );
  }

  if (reports.isError) {
    return (
      <div data-testid="daily-brief-error" className="card mb-3 border border-red-300/30 bg-red-400/[0.06] p-4 text-[13px] text-red-100" role="alert">
        今日建議暫時無法載入。
      </div>
    );
  }

  if (!latestDate) {
    return (
      <div data-testid="daily-brief-empty" className="card mb-3 border border-white/10 bg-white/[0.03] p-4" role="status">
        <div className="text-[12px] font-semibold text-white/90">今日建議</div>
        <p className="mt-1 text-[13px] text-[var(--muted)]">UNKNOWN：尚無今日建議</p>
      </div>
    );
  }

  const brief = cryptoBrief(structured.data);
  const thesis = String(brief.investment_thesis_one_liner ?? "").trim();
  const exec = Array.isArray(brief.exec_summary)
    ? brief.exec_summary.map((line) => String(line ?? "").trim()).filter(Boolean)
    : [];
  const take = firstTake(detail.isError ? null : detail.data);

  return (
    <section data-testid="daily-brief-panel" className="card mb-3 p-4">
      <div className="card-title">今日建議</div>
      <div data-testid="daily-brief-date" className="mt-1 font-mono text-[12px] text-cyan-200">{latestDate}</div>
      {thesis ? (
        <p data-testid="daily-brief-thesis" className="mt-2 text-[14px] leading-snug text-white">{thesis}</p>
      ) : null}
      {exec.length ? (
        <ul data-testid="daily-brief-exec-summary" className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-[var(--muted)]">
          {exec.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
      <div data-testid="daily-brief-ai-interpretation" className="mt-3">
        <div className="text-[11px] font-semibold text-white/45">AI 解讀</div>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--muted)]">{aiInterpretation(take)}</p>
      </div>
      <Link to={`/report/${latestDate}`} data-testid="daily-brief-report-link" className="mt-3 inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5">
        查看完整 brief
      </Link>
    </section>
  );
}
