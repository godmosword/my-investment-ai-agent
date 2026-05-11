import { useReports, useStructuredReports, useIndustryThemes } from "../../../hooks/useApi";

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
  const { data: themePayload, isLoading: thLoading, error: thError } = useIndustryThemes(80);
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

      <div className="card" style={{ marginBottom: 12 }} data-testid="industries-m5-api">
        <div className="card-title">產業主題 API（M5）</div>
        <div className="page-subtitle" style={{ marginBottom: 8 }}>
          <code>/api/industries/themes</code> — 靜態主題卡 + 意圖樣本 regime（非即時付費資料）。
        </div>
        {thLoading && <div className="loading" style={{ padding: "8px 0", fontSize: 12 }}>載入主題…</div>}
        {thError && !thLoading && (
          <div className="error-msg" style={{ fontSize: 12 }}>
            無法載入主題：<code>{thError.message}</code>
          </div>
        )}
        {!thLoading && !thError && themePayload && (
          <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
            <div>
              意圖筆數：<b style={{ color: "var(--text)" }}>{themePayload.intent_count ?? 0}</b>
              {themePayload.intent_sample_regime != null ? (
                <>
                  {" "}
                  · 樣本 regime：<b style={{ color: "var(--text)" }}>{String(themePayload.intent_sample_regime)}</b>
                </>
              ) : null}
            </div>
            {(themePayload.themes ?? []).length > 0 ? (
              <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                {(themePayload.themes ?? []).slice(0, 12).map((t) => (
                  <li key={t.id ?? t.label ?? JSON.stringify(t)} style={{ marginBottom: 4 }}>
                    {typeof t === "string" ? t : t.label ?? t.id ?? "—"}
                  </li>
                ))}
              </ul>
            ) : (
              <div style={{ marginTop: 8 }}>無靜態主題列。</div>
            )}
          </div>
        )}
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
