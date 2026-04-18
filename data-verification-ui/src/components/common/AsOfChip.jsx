import { formatAsOfZh } from "../../utils/formatAsOfZh";

/**
 * 審計用「as-of」標籤：時間戳 + 可選資料來源（對齊 BLOOMBERG Phase 0 §2）
 */
export default function AsOfChip({
  asOf,
  source,
  label = "更新",
  polling = false,
  className = "",
}) {
  const text = formatAsOfZh(asOf);
  return (
    <span
      className={`qs-asof-chip inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-[rgba(120,160,200,0.18)] bg-[rgba(12,18,34,0.65)] px-2.5 py-1 text-[11px] leading-snug text-[var(--muted)] ${className}`}
      data-testid="as-of-chip"
    >
      <span className="font-medium text-[var(--text)]">{label}</span>
      <span className="font-mono text-[12px] text-[var(--text)]">{text}</span>
      {source ? (
        <span className="truncate text-[var(--muted)]" title={source}>
          · {source}
        </span>
      ) : null}
      {polling ? (
        <span className="text-[10px] text-[var(--accent)]" data-testid="as-of-chip-polling">
          輪詢中
        </span>
      ) : null}
    </span>
  );
}
