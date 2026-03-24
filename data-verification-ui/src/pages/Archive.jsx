import { Link } from "react-router-dom";
import { useReports } from "../hooks/useApi";

function regimeLabel(score) {
  if (score == null) return null;
  if (score >= 3.5) return { text: "Risk OFF", color: "var(--red)" };
  if (score >= 2.5) return { text: "中性", color: "var(--yellow)" };
  return { text: "Risk ON", color: "var(--green)" };
}

export default function Archive() {
  const { data: reports, isLoading, error } = useReports(60);

  if (isLoading) return <div className="loading">載入歷史報告…</div>;
  if (error)     return <div className="error-msg">載入失敗：{error.message}</div>;
  if (!reports?.length) return <div className="loading">尚無歷史報告</div>;

  return (
    <>
      <div className="page-header">
        <div className="page-title">報告存檔</div>
        <div className="page-subtitle">共 {reports.length} 份日報</div>
      </div>

      {reports.map((r, i) => {
        const regime = regimeLabel(r.avg_risk_score);
        const date = r.report_date ?? r.timestamp?.slice(0, 10) ?? "—";
        return (
          <Link key={i} to={`/report/${date}`} className="archive-item">
            <div className="archive-date">{date}</div>
            <div className="archive-meta">
              {regime && (
                <span>
                  市場模式 <strong style={{ color: regime.color }}>{regime.text}</strong>
                </span>
              )}
              {r.dxy != null && (
                <span>DXY <strong>{r.dxy.toFixed(2)}</strong></span>
              )}
              {r.mvrv_z_score != null && (
                <span>MVRV <strong>{r.mvrv_z_score.toFixed(2)}</strong></span>
              )}
              {r.etf_flow_millions != null && (
                <span>
                  ETF{" "}
                  <strong style={{ color: r.etf_flow_millions >= 0 ? "var(--green)" : "var(--red)" }}>
                    {r.etf_flow_millions > 0 ? "+" : ""}{r.etf_flow_millions}億
                  </strong>
                </span>
              )}
            </div>
          </Link>
        );
      })}
    </>
  );
}
