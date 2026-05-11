import { Link } from "react-router-dom";
import { DEFAULT_GATE_STATUS } from "../constants/gateDisplay";
import GateStatusBadge from "./common/GateStatusBadge";
import { useGateStatus, useReports } from "../hooks/useApi";

/**
 * Map reviewer-loop gate_status → GateStatusBadge variant.
 * pass→pass, fail→critical, degraded→warn, 其他（含未審）→info.
 */
function variantFor(status) {
  if (status === "pass") return "pass";
  if (status === "fail") return "critical";
  if (status === "degraded") return "warn";
  return "info";
}

/** Appends ` (Nr)` when revision_count > 0 (pass / fail / degraded). */
function revisionSuffix(revisionCount) {
  const n = Number(revisionCount);
  if (!Number.isFinite(n) || n <= 0) return "";
  return ` (${n}r)`;
}

/**
 * Global Gate Failure header indicator — latest report's reviewer-loop verdict.
 * Visible in `Shell` so failures surface without opening Quant/Brief module.
 * Click-through to that day's `/report/:date`.
 */
export default function GlobalGateBadge() {
  const reportsQ = useReports(1);
  const latest = Array.isArray(reportsQ.data) ? reportsQ.data[0] : null;
  const date = latest?.report_date ?? latest?.date ?? null;
  const gateQ = useGateStatus(date);

  if (!date) return null;

  const status = gateQ.data?.gate_status ?? DEFAULT_GATE_STATUS;
  const variant = variantFor(status);
  const revisions = gateQ.data?.revision_count ?? 0;
  const rev = revisionSuffix(revisions);
  const label = status === "fail"
    ? `Gate FAIL${rev} · ${date}`
    : status === "degraded"
    ? `Gate DEGRADED${rev} · ${date}`
    : status === "pass"
    ? `Gate pass${rev} · ${date}`
    : `Gate ${DEFAULT_GATE_STATUS} · ${date}`;

  return (
    <Link
      to={`/report/${date}`}
      data-testid="global-gate-badge"
      data-gate-status={status}
      title="檢視最新日報 Reviewer Loop 結果"
      className="no-underline"
    >
      <GateStatusBadge variant={variant}>{label}</GateStatusBadge>
    </Link>
  );
}
