/** Aligns with ``brief_profiles.PROFILES`` keys (modularization Phase 2). */
export const REPORT_PROFILE_IDS = ["full", "lite", "crypto-only"];

/** @param {string | null | undefined} raw */
export function normalizeReportProfile(raw) {
  const p = String(raw ?? "full")
    .trim()
    .toLowerCase();
  return REPORT_PROFILE_IDS.includes(p) ? p : "full";
}
