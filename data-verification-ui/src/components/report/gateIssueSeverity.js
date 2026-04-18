/**
 * Gate issue 文案粗分級（無後端結構化欄位時的字串啟發式）。
 * @param {unknown} line
 * @returns {"critical" | "warn" | "info"}
 */
export function classifyGateIssue(line) {
  const raw = String(line ?? "");
  const u = raw.toUpperCase();

  if (
    u.includes("CRITICAL") ||
    u.includes("BLOCK") ||
    u.includes("FAIL") ||
    raw.includes("阻擋") ||
    raw.includes("致命")
  ) {
    return "critical";
  }
  if (
    u.includes("WARN") ||
    u.includes("STALE") ||
    u.includes("MISSING") ||
    u.includes("DATA_MISSING") ||
    raw.includes("缺失") ||
    raw.includes("警告") ||
    raw.includes("過期")
  ) {
    return "warn";
  }
  return "info";
}

/** @param {unknown} line */
export function gateIssueLiClass(line) {
  return `gate-issue-li gate-issue-li--${classifyGateIssue(line)}`;
}
