import { useReportProfileStats } from "../../hooks/useApi";
import { REPORT_PROFILE_IDS, normalizeReportProfile } from "./reportProfiles";

/**
 * Visualization V3 — Archive 小圖：displays per-profile report counts within a
 * recent window as a horizontal bar chart. Backed by ``GET /api/reports/profile-stats``.
 *
 * Designed to sit under the Archive page header so users can see the
 * distribution of `full` / `lite` / `crypto-only` runs at a glance, and jump
 * into a filtered list with one click.
 *
 * @param {object} props
 * @param {number} [props.days=30]
 * @param {string} [props.activeProfile]
 * @param {(profile: string) => void} [props.onSelect]
 * @param {string} [props.className]
 */
export default function BriefProfileStatsBar({
  days = 30,
  activeProfile,
  onSelect,
  className = "",
}) {
  const { data, isLoading, error } = useReportProfileStats(days);

  if (isLoading) {
    return (
      <div
        className={`text-[12px] text-[var(--muted)] ${className}`}
        data-testid="profile-stats-bar-loading"
      >
        載入版型分布…
      </div>
    );
  }
  if (error) {
    return (
      <div
        className={`text-[12px] text-[var(--red)] ${className}`}
        data-testid="profile-stats-bar-error"
      >
        版型分布載入失敗：{error.message}
      </div>
    );
  }
  if (!data || !data.breakdown?.length) {
    return null;
  }

  // Sort by canonical profile order; unknown profiles go last.
  const breakdown = [...data.breakdown].sort((a, b) => {
    const ia = REPORT_PROFILE_IDS.indexOf(a.profile);
    const ib = REPORT_PROFILE_IDS.indexOf(b.profile);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  const maxCount = Math.max(1, ...breakdown.map((r) => r.report_count));
  const active = normalizeReportProfile(activeProfile);

  return (
    <div
      className={`flex flex-col gap-1.5 ${className}`}
      data-testid="profile-stats-bar"
    >
      <div className="text-[12px] text-[var(--muted)]">
        近 {data.window_days} 天共 {data.total_reports} 份（依 BQ llm_run_log 彙總）
      </div>
      <div className="flex flex-col gap-1">
        {breakdown.map((row) => {
          const pct = (row.report_count / maxCount) * 100;
          const isActive = row.profile === active;
          return (
            <button
              key={row.profile}
              type="button"
              onClick={() => onSelect?.(row.profile)}
              className="group flex items-center gap-2 text-left"
              data-testid={`profile-stats-row-${row.profile}`}
              aria-pressed={isActive}
              title={
                row.latest_date
                  ? `最新：${row.latest_date}`
                  : "目前無紀錄"
              }
            >
              <span
                className="w-[80px] shrink-0 font-mono text-[11px]"
                style={{ color: isActive ? "var(--text)" : "var(--muted)" }}
              >
                {row.profile}
              </span>
              <span className="relative h-[6px] flex-1 overflow-hidden rounded-full bg-[rgba(120,160,200,0.12)]">
                <span
                  className="absolute inset-y-0 left-0 rounded-full transition-all"
                  style={{
                    width: `${pct}%`,
                    background: isActive
                      ? "var(--accent, #6ea8ff)"
                      : "rgba(120,160,200,0.55)",
                  }}
                />
              </span>
              <span
                className="w-[40px] shrink-0 text-right font-mono text-[11px]"
                style={{ color: isActive ? "var(--text)" : "var(--muted)" }}
              >
                {row.report_count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
