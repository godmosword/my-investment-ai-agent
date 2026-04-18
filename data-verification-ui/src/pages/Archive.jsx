import { Link, useSearchParams } from "react-router-dom";
import { useEffect } from "react";
import { useReports } from "../hooks/useApi";
import { regimeInfo } from "../utils/regime";
import SymbolFocusBar from "../components/SymbolFocusBar";
import { normalizeReportProfile } from "../components/report/reportProfiles";
import BriefProfileBar from "../components/report/BriefProfileBar";
import BriefProfileStatsBar from "../components/report/BriefProfileStatsBar";

const STRUCTURED_FLAG = import.meta.env.VITE_STRUCTURED_REPORT === "1";

export default function Archive() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawProfile = searchParams.get("profile");
  const profile = normalizeReportProfile(rawProfile);

  useEffect(() => {
    const cur = searchParams.get("profile");
    const n = normalizeReportProfile(cur);
    if (cur != null && cur !== "" && n !== cur) {
      const next = new URLSearchParams(searchParams);
      next.set("profile", n);
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const profileQs = STRUCTURED_FLAG ? `?profile=${encodeURIComponent(profile)}` : "";
  const { data: reports, isLoading, error } = useReports(60, STRUCTURED_FLAG ? profile : null);

  if (isLoading) {
    return (
      <>
        <SymbolFocusBar compact />
        <div className="loading">載入歷史報告…</div>
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
  if (!reports?.length) {
    return (
      <>
        <SymbolFocusBar compact />
        <div className="loading">尚無歷史報告</div>
      </>
    );
  }

  return (
    <>
      <SymbolFocusBar compact />
      <div className="page-header">
        <div className="page-title">報告存檔</div>
        <div
          className="page-subtitle"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "8px 12px",
          }}
        >
          <span>
            共 {reports.length} 份日報
            {STRUCTURED_FLAG ? (
              <span style={{ marginLeft: 8, fontSize: 12, color: "var(--muted)" }}>
                （列表依 BQ「{profile}」pipeline 紀錄篩選）
              </span>
            ) : null}
          </span>
          {STRUCTURED_FLAG ? (
            <BriefProfileBar
              value={profile}
              onChange={(next) => {
                const n = normalizeReportProfile(next);
                const nextParams = new URLSearchParams(searchParams);
                nextParams.set("profile", n);
                setSearchParams(nextParams, { replace: true });
              }}
            />
          ) : null}
        </div>
        {STRUCTURED_FLAG ? (
          <BriefProfileStatsBar
            className="mt-3 max-w-md"
            days={30}
            activeProfile={profile}
            onSelect={(next) => {
              const n = normalizeReportProfile(next);
              const nextParams = new URLSearchParams(searchParams);
              nextParams.set("profile", n);
              setSearchParams(nextParams, { replace: true });
            }}
          />
        ) : null}
      </div>

      {reports.map((r, i) => {
        const regime = regimeInfo(r.avg_risk_score);
        const date = r.report_date ?? r.timestamp?.slice(0, 10) ?? "—";
        return (
          <Link key={i} to={`/report/${date}${profileQs}`} className="archive-item">
            <div className="archive-date">{date}</div>
            <div className="archive-meta">
              {r.avg_risk_score != null && (
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
