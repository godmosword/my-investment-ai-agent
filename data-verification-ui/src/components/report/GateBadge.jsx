/**
 * FE-2 — compact gate pass/fail badge for the Daily Brief header.
 *
 * Renders based on ``payload.gate_summary``:
 *   - ``available === false`` (or missing) → no badge
 *   - ``ok === true``                       → green "Gate ✓"
 *   - ``ok === false``                      → red "Gate ✗ (N)" with issue count
 */
export default function GateBadge({ gateSummary }) {
  if (!gateSummary || gateSummary.available !== true) return null;

  const ok = gateSummary.ok === true;
  const fail = gateSummary.ok === false;
  if (!ok && !fail) return null;

  const count = Array.isArray(gateSummary.issues) ? gateSummary.issues.length : 0;
  const label = ok ? "Gate ✓" : `Gate ✗${count > 0 ? ` (${count})` : ""}`;
  const tone = ok ? "gate-badge--ok" : "gate-badge--fail";
  const title = ok ? "本次戰報通過 Gate 檢查" : `本次戰報未通過 Gate 檢查${count > 0 ? `（${count} 項問題）` : ""}`;

  return (
    <span
      className={`gate-badge ${tone}`}
      data-testid="brief-gate-badge"
      data-gate-ok={ok ? "1" : "0"}
      role="status"
      title={title}
      aria-label={title}
    >
      {label}
    </span>
  );
}
