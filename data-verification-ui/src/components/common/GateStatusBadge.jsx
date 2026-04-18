/**
 * Gate 摘要狀態（對應 `validate_report`；V2 後可接 API）
 * variant: pass | warn | critical | info
 */
export default function GateStatusBadge({
  variant = "pass",
  children,
  className = "",
}) {
  const base =
    "qs-gate-badge inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium";
  const styles = {
    pass: "border border-emerald-500/35 bg-emerald-500/10 text-emerald-300",
    warn: "border border-amber-500/40 bg-amber-500/12 text-amber-200",
    critical: "border border-rose-500/45 bg-rose-500/12 text-rose-200",
    info: "border border-slate-500/35 bg-slate-500/10 text-slate-200",
  };
  const v = styles[variant] ? variant : "info";
  return (
    <span className={`${base} ${styles[v]} ${className}`} data-testid={`gate-badge-${v}`}>
      {children}
    </span>
  );
}
