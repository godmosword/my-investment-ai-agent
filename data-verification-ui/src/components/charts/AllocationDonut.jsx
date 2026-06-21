import { useMemo } from "react";
import { palette } from "../../design/tokens";
import { ChartEmpty } from "./ChartStates";

/**
 * 持倉配置 donut（純 SVG）。slice 由 weight 正規化（容忍 weight 為百分比或分數）。
 * 數字由 portfolio API 注入，前端只正規化顯示、不重算估值（無數據幻覺紅線）。
 *
 * @param {{ holdings?: Array<{symbol?:string, weight?:number, market_value?:number}>, size?:number }} props
 */
const SLICE_COLORS = [
  palette.accent, // #22d3ee
  palette.regime.on, // #34d399
  palette.accent2, // #f59e0b
  "#a78bfa",
  "#f472b6",
  "#60a5fa",
  "#fbbf24",
  "#4ade80",
];

function fin(v) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

export default function AllocationDonut({ holdings = [], size = 168 }) {
  const slices = useMemo(() => {
    const items = holdings
      .map((h) => ({ symbol: String(h?.symbol || "—"), weight: fin(h?.weight) }))
      .filter((h) => h.weight > 0);
    const total = items.reduce((s, h) => s + h.weight, 0);
    if (total <= 0) return [];
    return items
      .sort((a, b) => b.weight - a.weight)
      .map((h, i) => ({ ...h, frac: h.weight / total, color: SLICE_COLORS[i % SLICE_COLORS.length] }));
  }, [holdings]);

  if (slices.length === 0) return <ChartEmpty label="尚無持倉配置" />;

  const stroke = 18;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div data-testid="allocation-donut" className="flex flex-wrap items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="持倉配置">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(120,160,200,0.12)" strokeWidth={stroke} />
        {slices.map((s) => {
          const len = s.frac * circ;
          const el = (
            <circle
              key={s.symbol}
              data-testid="allocation-slice"
              data-symbol={s.symbol}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${len} ${circ - len}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cy})`}
            />
          );
          offset += len;
          return el;
        })}
        <text x={cx} y={cy - 2} textAnchor="middle" className="fill-white/85" fontSize="13" fontWeight="600">
          {slices.length}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="fill-white/45" fontSize="9">
          持倉
        </text>
      </svg>
      <ul className="flex min-w-[120px] flex-1 flex-col gap-1 text-[12px]">
        {slices.map((s) => (
          <li key={s.symbol} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
              <span className="font-mono text-white/85">{s.symbol}</span>
            </span>
            <span className="text-white/55">{(s.frac * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
