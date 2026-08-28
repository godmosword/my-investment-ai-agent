import { Link } from "react-router-dom";
import { useDataHealth, useReport, useReports } from "../../../hooks/useApi";

function aiInterpretation(value) {
  const text = String(value ?? "").trim();
  return text || "UNKNOWN／未提供";
}

function reportListRows(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.reports)) return data.reports;
  return [];
}

function latestReportDate(data) {
  for (const row of reportListRows(data)) {
    const date = String(row?.report_date ?? row?.date ?? "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(date)) return date;
  }
  return "";
}

function firstTake(report) {
  if (!report || typeof report !== "object") return "";
  return report.gemini_take || report.grok_summary || report.gpt_summary || "";
}

export default function DailyBriefHonesty() {
  const health = useDataHealth();
  const reports = useReports(5);
  const latestDate = latestReportDate(reports.data);
  const detail = useReport(latestDate);
  const dailySource = (health.data?.items || []).find((item) => item?.id === "reports");

  const isLoading =
    health.isLoading || reports.isLoading || (Boolean(latestDate) && detail.isLoading);
  const isError = Boolean(reports.isError);

  if (isLoading) {
    return (
      <div
        className="card mb-3 p-3 text-[13px] text-[var(--muted)]"
        data-testid="daily-brief-loading"
        role="status"
      >
        載入今日建議…
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="card mb-3 p-3 text-[13px] text-red-300"
        data-testid="daily-brief-error"
        role="alert"
      >
        今日建議暫時無法載入。
      </div>
    );
  }

  if (!latestDate) {
    return (
      <div
        className="card mb-3 p-3 text-[13px] text-[var(--muted)]"
        data-testid="daily-brief-empty"
        role="status"
      >
        UNKNOWN：尚無今日建議
      </div>
    );
  }

  const date = String(detail.data?.report_date ?? latestDate).trim() || latestDate;
  const take = firstTake(detail.data);

  return (
    <div className="card mb-3 p-3" data-testid="daily-brief-panel">
      <div className="card-title">今日建議</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] text-white/70">
        <span data-testid="daily-brief-date" className="font-mono text-white/85">
          {date}
        </span>
        {dailySource?.status ? (
          <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-[10px] uppercase text-white/50">
            {dailySource.status}
          </span>
        ) : null}
      </div>
      <div data-testid="daily-brief-ai-interpretation" className="mt-2">
        <div className="text-[11px] font-semibold text-white/45">AI 解讀</div>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--muted)]">{aiInterpretation(take)}</p>
      </div>
      <Link
        to={`/report/${date}`}
        data-testid="daily-brief-report-link"
        className="mt-3 inline-flex min-h-[36px] items-center rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/75 hover:bg-white/5"
      >
        查看日報
      </Link>
    </div>
  );
}
