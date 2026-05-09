import { Link, useSearchParams } from "react-router-dom";
import { useEffect } from "react";
import { useReports, useGateStatus } from "../hooks/useApi";
import { regimeInfo } from "../utils/regime";
import SymbolFocusBar from "../components/SymbolFocusBar";
import { normalizeReportProfile } from "../components/report/reportProfiles";
import BriefProfileStatsBar from "../components/report/BriefProfileStatsBar";

const PROFILE_STORAGE_KEY = "qsi_report_profile";

const GATE_BADGE_CONFIG = {
  pass:     { label: "通過", color: "var(--green, #22c55e)" },
  fail:     { label: "需修正", color: "var(--amber, #f59e0b)" },
  degraded: { label: "降級", color: "var(--red, #ef4444)" },
  "未審":   { label: "未審", color: "var(--muted, #6b7280)" },
};

function GateBadge({ date }) {
  const { data, isError } = useGateStatus(date);
  // Defensive: on API error fall back to grey 未審
  const status = isError ? "未審" : (data?.gate_status ?? "未審");
  const cfg = GATE_BADGE_CONFIG[status] ?? GATE_BADGE_CONFIG["未審"];
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.02em",
        color: cfg.color,
        border: `1px solid ${cfg.color}`,
        borderRadius: 4,
        padding: "1px 5px",
        fontFamily: "var(--font-mono, monospace)",
        flexShrink: 0,
      }}
    >
      {cfg.label}
    </span>
  );
}

const STRUCTURED_FLAG = import.meta.env.VITE_STRUCTURED_REPORT === "1";

const PROFILE_CARDS = [
  {
    id: "full",
    label: "Full",
    zh: "完整版",
    desc: "總體宏觀、加密、AI 股、新聞、QSREC 全部收錄。最大深度。",
  },
  {
    id: "lite",
    label: "Lite",
    zh: "精簡版",
    desc: "加密 + AI 股票。略去宏觀與時事圓桌，閱讀更快。",
  },
  {
    id: "crypto-only",
    label: "Crypto",
    zh: "幣圈版",
    desc: "僅含加密貨幣區塊。不含股票內容。",
  },
];

function ProfileCardPicker({ value, onChange }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 8,
        marginBottom: 16,
      }}
      data-testid="profile-card-picker"
    >
      {PROFILE_CARDS.map((c) => {
        const active = value === c.id;
        return (
          <button
            key={c.id}
            onClick={() => onChange(c.id)}
            style={{
              border: active
                ? "1.5px solid var(--accent, #6366f1)"
                : "1px solid var(--border, rgba(255,255,255,0.08))",
              borderRadius: 8,
              padding: "10px 12px",
              background: active
                ? "rgba(99,102,241,0.10)"
                : "var(--card-bg, rgba(255,255,255,0.04))",
              cursor: "pointer",
              textAlign: "left",
              transition: "border 0.15s, background 0.15s",
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 13,
                color: active ? "var(--accent, #6366f1)" : "var(--text)",
                marginBottom: 2,
              }}
            >
              {c.label}
              <span
                style={{
                  marginLeft: 5,
                  fontSize: 10,
                  fontWeight: 400,
                  color: "var(--muted)",
                }}
              >
                {c.zh}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.4 }}>
              {c.desc}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default function Archive() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawProfile = searchParams.get("profile");
  const profile = normalizeReportProfile(rawProfile);

  // Sync URL param ↔ localStorage on mount; validate to enum before writing.
  useEffect(() => {
    const cur = searchParams.get("profile");
    const n = normalizeReportProfile(cur);
    if (cur == null || cur === "") {
      // No URL param — restore from localStorage if present.
      try {
        const stored = normalizeReportProfile(localStorage.getItem(PROFILE_STORAGE_KEY));
        if (stored !== "full" || localStorage.getItem(PROFILE_STORAGE_KEY) === "full") {
          const next = new URLSearchParams(searchParams);
          next.set("profile", stored);
          setSearchParams(next, { replace: true });
        }
      } catch {
        // ignore storage errors
      }
    } else if (n !== cur) {
      // Coerce invalid param to canonical value.
      const next = new URLSearchParams(searchParams);
      next.set("profile", n);
      setSearchParams(next, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <div className="page-subtitle">
          共 {reports.length} 份日報
          {STRUCTURED_FLAG ? (
            <span style={{ marginLeft: 8, fontSize: 12, color: "var(--muted)" }}>
              （列表依 BQ「{profile}」pipeline 紀錄篩選）
            </span>
          ) : null}
        </div>
      </div>

      {STRUCTURED_FLAG ? (
        <ProfileCardPicker
          value={profile}
          onChange={(next) => {
            const n = normalizeReportProfile(next);
            try { localStorage.setItem(PROFILE_STORAGE_KEY, n); } catch { /* ignore */ }
            const nextParams = new URLSearchParams(searchParams);
            nextParams.set("profile", n);
            setSearchParams(nextParams, { replace: true });
          }}
        />
      ) : null}

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

      {reports.map((r, i) => {
        const regime = regimeInfo(r.avg_risk_score);
        const date = r.report_date ?? r.timestamp?.slice(0, 10) ?? "—";
        return (
          <Link key={i} to={`/report/${date}${profileQs}`} className="archive-item">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div className="archive-date">{date}</div>
              {STRUCTURED_FLAG && <GateBadge date={date} />}
            </div>
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
