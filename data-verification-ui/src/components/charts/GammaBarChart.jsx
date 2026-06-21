import { useMemo } from "react";
import { CHART_THEME } from "./themedChart";
import { ChartEmpty } from "./ChartStates";

/**
 * Per-strike net GEX 柱狀圖（純 SVG，x=strike）。0 軸上方正 gamma 綠、下方負 gamma 紅。
 * 可選 spot 價標記一條垂直線。數字由 API 注入，前端不重算（無數據幻覺紅線）；
 * 空資料 → ChartEmpty，不示意。
 *
 * @param {{ data?: Array<{strike:number, net_gex:number}>, spot?: number|null, height?: number }} props
 */
function fin(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function GammaBarChart({ data = [], spot = null, height = 180 }) {
  const points = useMemo(() => {
    const out = [];
    for (const d of data) {
      const strike = fin(d?.strike);
      const net = fin(d?.net_gex);
      if (strike == null || net == null) continue;
      out.push({ strike, net });
    }
    return out.sort((a, b) => a.strike - b.strike);
  }, [data]);

  if (points.length === 0) return <ChartEmpty label="尚無 per-strike GEX 資料" />;

  const W = 600;
  const H = height;
  const padX = 8;
  const padY = 16;
  const maxAbs = Math.max(...points.map((p) => Math.abs(p.net)), 1);
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;
  const zeroY = padY + innerH / 2;
  const slot = innerW / points.length;
  const barW = Math.max(2, Math.min(slot * 0.7, 28));
  const minStrike = points[0].strike;
  const maxStrike = points[points.length - 1].strike;
  const spotN = fin(spot);
  const spotX =
    spotN != null && maxStrike > minStrike
      ? padX + ((spotN - minStrike) / (maxStrike - minStrike)) * innerW
      : null;

  return (
    <div data-testid="gamma-bar-chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label="per-strike net gamma exposure"
      >
        {/* 0 軸 */}
        <line x1={padX} y1={zeroY} x2={W - padX} y2={zeroY} stroke={CHART_THEME.border} strokeWidth="1" />
        {/* spot 標記 */}
        {spotX != null ? (
          <line
            x1={spotX}
            y1={padY}
            x2={spotX}
            y2={H - padY}
            stroke={CHART_THEME.accent}
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        ) : null}
        {points.map((p, i) => {
          const cx = padX + slot * (i + 0.5);
          const h = (Math.abs(p.net) / maxAbs) * (innerH / 2);
          const up = p.net >= 0;
          const y = up ? zeroY - h : zeroY;
          return (
            <rect
              key={p.strike}
              data-testid="gamma-bar"
              data-strike={p.strike}
              x={cx - barW / 2}
              y={y}
              width={barW}
              height={Math.max(1, h)}
              fill={up ? CHART_THEME.up : CHART_THEME.down}
              opacity="0.85"
            />
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-white/40">
        <span>{minStrike}</span>
        <span>strike · 0 軸上方正 gamma（綠）/ 下方負 gamma（紅）{spotX != null ? "；虛線=spot" : ""}</span>
        <span>{maxStrike}</span>
      </div>
    </div>
  );
}
