import ProfileBadge from "../common/ProfileBadge";
import { REPORT_PROFILE_IDS } from "./reportProfiles";

/**
 * Visualization V3 — switch ``?profile=`` without touching the pipeline (read-only UI).
 */
export default function BriefProfileBar({ value, onChange, className = "" }) {
  const v = REPORT_PROFILE_IDS.includes(value) ? value : "full";

  return (
    <div
      className={`flex flex-wrap items-center gap-2 ${className}`}
      data-testid="brief-profile-bar"
    >
      <span className="text-[12px] text-[var(--muted)]">版型</span>
      <label htmlFor="brief-profile-select" className="sr-only">
        選擇日報版型
      </label>
      <select
        id="brief-profile-select"
        value={v}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-[rgba(120,160,200,0.25)] bg-[rgba(12,18,34,0.85)] px-2 py-1 font-mono text-[12px] text-[var(--text)]"
      >
        {REPORT_PROFILE_IDS.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
      <ProfileBadge profile={v} />
    </div>
  );
}
