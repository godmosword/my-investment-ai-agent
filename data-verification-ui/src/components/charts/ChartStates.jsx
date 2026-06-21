/**
 * 共用圖表資料狀態（loading / empty / missing）。
 * 紅線：缺料一律走 empty/missing，不以示意數據補洞。
 */

export function ChartLoading({ label = "載入中…" }) {
  return (
    <div data-testid="chart-loading" className="loading py-6 text-center text-[12px] text-white/50">
      {label}
    </div>
  );
}

export function ChartEmpty({ label = "尚無資料" }) {
  return (
    <div data-testid="chart-empty" className="py-6 text-center text-[12px] text-white/45">
      {label}
    </div>
  );
}

export function ChartMissing({ reason = "" }) {
  return (
    <div data-testid="chart-missing" className="py-6 text-center text-[12px] text-amber-200/70">
      資料不可得{reason ? `（${reason}）` : ""}
    </div>
  );
}
