/**
 * 日報版型標籤（對應 `REPORT_PROFILE` / modularization Phase 2）
 */
export default function ProfileBadge({ profile = "full", className = "" }) {
  const p = String(profile || "full").toLowerCase();
  const label =
    p === "lite" ? "lite" : p === "crypto-only" || p === "crypto_only" ? "crypto-only" : "full";
  return (
    <span
      className={`qs-profile-badge inline-flex items-center rounded-md border border-[rgba(139,92,246,0.35)] bg-[rgba(139,92,246,0.12)] px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--accent2)] ${className}`}
      data-testid={`profile-badge-${label}`}
      title={`報告版型：${label}`}
    >
      {label}
    </span>
  );
}
