import { useReports, useStructuredReports } from "../../../hooks/useApi";

function extractIndustryTrendsBlock(structuredReport) {
  if (!structuredReport) return null;
  const blocks = structuredReport.blocks ?? [];
  const block = blocks.find(
    (b) => typeof b === "string" && b.toLowerCase().includes("industry_trends")
  );
  if (block) return block;
  // Also check report metadata fields
  const meta = structuredReport.metadata ?? {};
  if (meta.industry_trends) return meta.industry_trends;
  return null;
}

function DayBlock({ date, report, isLoading }) {
  if (isLoading) {
    return (
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-title" style={{ fontSize: 12, color: "var(--muted)" }}>{date}</div>
        <div className="loading" style={{ padding: "8px 0", fontSize: 12 }}>載入中…</div>
      </div>
    );
  }

  const block = extractIndustryTrendsBlock(report);
  if (!block) return null;

  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div className="card-title" style={{ fontSize: 12, color: "var(--muted)" }}>{date}</div>
      <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {typeof block === "string" ? block : JSON.stringify(block, null, 2)}
      </div>
    </div>
  );
}

export default function IndustriesHome() {
  const { data: reports } = useReports(3);
  const dates = reports?.map((r) => r.report_date) ?? [];
  const structuredResults = useStructuredReports(dates, "full");

  const hasAnyTrends = structuredResults.some(
    (r) => !r.isLoading && extractIndustryTrendsBlock(r.data)
  );
  const allLoaded = dates.length > 0 && structuredResults.every((r) => !r.isLoading);

  return (
    <>
      <div className="page-header">
        <div className="page-title">產業趨勢</div>
        <div className="page-subtitle">近 3 日日報 industry_trends 區塊</div>
      </div>

      {dates.length === 0 && (
        <div className="card" style={{ color: "var(--muted)", fontSize: 13 }}>
          尚無報告資料。
        </div>
      )}

      {dates.map((date, i) => (
        <DayBlock
          key={date}
          date={date}
          report={structuredResults[i]?.data}
          isLoading={structuredResults[i]?.isLoading ?? true}
        />
      ))}

      {allLoaded && !hasAnyTrends && dates.length > 0 && (
        <div className="card" style={{ color: "var(--muted)", fontSize: 13 }}>
          近 3 日報告均未包含 industry_trends 區塊。
        </div>
      )}
    </>
  );
}
