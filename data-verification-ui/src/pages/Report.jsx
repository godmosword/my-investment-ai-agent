import { useParams, Link } from "react-router-dom";
import { useReport, useStructuredReport } from "../hooks/useApi";
import MetricCard from "../components/MetricCard";
import TradeCard from "../components/TradeCard";
import SymbolFocusBar from "../components/SymbolFocusBar";
import StructuredReportView from "../components/report/StructuredReportView";

const STRUCTURED_FLAG = import.meta.env.VITE_STRUCTURED_REPORT === "1";

export default function Report() {
  const { date } = useParams();
  const legacy = useReport(date, { enabled: !STRUCTURED_FLAG });
  const structured = useStructuredReport(date, "full", { enabled: STRUCTURED_FLAG });
  const active = STRUCTURED_FLAG ? structured : legacy;
  const { data: report, isLoading, error } = active;

  if (isLoading) {
    return (
      <>
        <SymbolFocusBar compact />
        <div className="loading">載入中…</div>
      </>
    );
  }
  if (error) {
    return (
      <>
        <SymbolFocusBar compact />
        <div className="error-msg">載入失敗：{error.message}</div>
      </>
    );
  }
  if (!report) {
    return (
      <>
        <SymbolFocusBar compact />
        <div className="loading">查無此報告</div>
      </>
    );
  }

  if (useStructured) {
    return <StructuredReportView reportDate={date} payload={report} />;
  }

  return (
    <>
      <SymbolFocusBar compact />
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <Link to="/archive" style={{ color: "var(--muted)", textDecoration: "none", fontSize: 14 }}>
            ← 返回
          </Link>
        </div>
        <div className="page-title">{date}</div>
        <div className="page-subtitle">每日投資戰報</div>
      </div>

      <div className="metrics-grid">
        <MetricCard label="DXY" value={report.dxy} format={(v) => v.toFixed(2)} />
        <MetricCard
          label="ETF 資金流"
          value={report.etf_flow_millions}
          unit="億"
          format={(v) => (v > 0 ? `+${v}` : `${v}`)}
        />
        <MetricCard label="MVRV Z" value={report.mvrv_z_score} format={(v) => v.toFixed(2)} />
        <MetricCard
          label="風險評分"
          value={report.avg_risk_score}
          unit="/5"
          format={(v) => v.toFixed(1)}
        />
      </div>

      {report.sentiment_score != null && (
        <div className="card">
          <div className="card-title">情緒指標</div>
          <div style={{ display: "flex", gap: 16, fontSize: 13 }}>
            <span>情緒分數 <strong>{report.sentiment_score?.toFixed(2)}</strong></span>
            {report.sopr != null && <span>SOPR <strong>{report.sopr?.toFixed(3)}</strong></span>}
            {report.exchange_netflow != null && (
              <span>交易所淨流向 <strong>{report.exchange_netflow}K BTC</strong></span>
            )}
          </div>
        </div>
      )}

      {report.grok_summary && (
        <>
          <div className="section-header">🔮 幣圈情報</div>
          <div className="summary-block">{report.grok_summary}</div>
        </>
      )}

      {report.gpt_summary && (
        <>
          <div className="section-header">🤖 AI 產業情報</div>
          <div className="summary-block">{report.gpt_summary}</div>
        </>
      )}

      {report.news_titles && (
        <>
          <div className="section-header">📰 新聞摘要</div>
          <div className="card">
            {report.news_titles.split("\n").map((line, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--muted)", padding: "3px 0", borderBottom: "1px solid var(--border)" }}>
                {line}
              </div>
            ))}
          </div>
        </>
      )}

      {report.recommendations?.length > 0 && (
        <>
          <div className="section-header">💼 交易建議 ({report.recommendations.length})</div>
          {report.recommendations.map((t, i) => (
            <TradeCard key={i} trade={t} />
          ))}
        </>
      )}
    </>
  );
}
