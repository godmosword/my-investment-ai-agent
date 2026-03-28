import { useState, useMemo } from "react";
import {
  AreaChart, Area,
  LineChart, Line,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { useMetricsHistory, useTradesPerformance } from "../hooks/useApi";
import {
  MOCK_EQUITY_CURVE,
  MOCK_WIN_LOSS_PIE,
  useMockCharts,
} from "../utils/mockPerformance";

const PERIODS = [
  { label: "30d", days: 30 },
  { label: "60d", days: 60 },
  { label: "90d", days: 90 },
];

function fmt(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" });
}

function fmtEquityDate(d) {
  if (!d) return "";
  return new Date(d).toLocaleDateString("zh-TW", { month: "short", day: "numeric" });
}

function ChartCard({ title, children }) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      {children}
    </div>
  );
}

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  color: "var(--text)",
  fontSize: 12,
};

/** 將 API 曲線或 mock 列正規化為圖表列 */
function normalizeEquityRows(curve, isMock) {
  const src = Array.isArray(curve) && curve.length ? curve : isMock ? MOCK_EQUITY_CURVE : [];
  return src.map((row) => ({
    ...row,
    label: row.label ?? fmtEquityDate(row.date),
    cumulative_pnl: row.cumulative_pnl != null ? Number(row.cumulative_pnl) : null,
  }));
}

function normalizePie(perf, isMock) {
  if (isMock) return [...MOCK_WIN_LOSS_PIE];
  const wins = Number(perf?.wins) || 0;
  const losses = Number(perf?.losses) || 0;
  const out = [];
  if (wins > 0) out.push({ name: "命中目標", value: wins, fill: "#10b981" });
  if (losses > 0) out.push({ name: "觸發停損", value: losses, fill: "#ef4444" });
  return out;
}

export default function Charts() {
  const [days, setDays] = useState(30);
  const envMock = useMockCharts();
  const { data, isLoading: mLoading, error: mError } = useMetricsHistory(days);
  const { data: perf, isLoading: pLoading, error: pError } = useTradesPerformance(days);

  const useDemoPerformance = envMock || !!pError;

  const equityRows = useMemo(() => {
    if (useDemoPerformance) {
      return normalizeEquityRows(null, true);
    }
    return normalizeEquityRows(perf?.equity_curve, false);
  }, [perf, useDemoPerformance]);

  const pieData = useMemo(() => {
    return normalizePie(perf, useDemoPerformance);
  }, [perf, useDemoPerformance]);

  const hasMetrics = !mError && Array.isArray(data) && data.length > 0;
  const rows = hasMetrics ? data.map((r) => ({ ...r, label: fmt(r.timestamp) })) : [];

  const perfSectionLoading = pLoading && !useDemoPerformance;
  const hasEquityChart = equityRows.length > 0 && equityRows.some((r) => r.cumulative_pnl != null);
  const hasPie = pieData.length > 0;

  return (
    <>
      <div className="page-header">
        <div className="page-title">指標圖表</div>
        <div className="page-subtitle">Glassbox · 累計 PnL 與勝率分布</div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {PERIODS.map(({ label, days: d }) => (
          <button
            key={d}
            type="button"
            onClick={() => setDays(d)}
            style={{
              padding: "5px 14px",
              borderRadius: 6,
              border: "1px solid",
              borderColor: days === d ? "var(--accent)" : "var(--border)",
              background: days === d ? "rgba(0,212,170,.12)" : "transparent",
              color: days === d ? "var(--accent)" : "var(--muted)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── 交易績效（Recharts：Area 淨值 + 甜甜圈）；API 失敗時示範資料 ── */}
      {useDemoPerformance && (
        <div className="glassbox-demo-banner" role="status">
          {pError
            ? <>無法載入 <code>/api/trades/performance</code>：{pError.message}。以下為<strong>示範曲線</strong>，非實盤。</>
            : <>已啟用 <code>VITE_GLASSBOX_MOCK=1</code>：顯示<strong>示範資料</strong>。</>}
        </div>
      )}

      {perfSectionLoading && (
        <div className="loading" style={{ padding: "20px", marginBottom: 12 }}>
          載入交易績效…
        </div>
      )}

      {!perfSectionLoading && (
        <>
          <ChartCard title="累計 PnL 曲線（已平倉加總 %）">
            {hasEquityChart ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={equityRows}>
                  <defs>
                    <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00d4aa" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#00d4aa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} width={44} />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v) => [`${Number(v).toFixed(2)}%`, "累計 PnL"]}
                  />
                  <ReferenceLine y={0} stroke="var(--border)" />
                  <Area
                    type="monotone"
                    dataKey="cumulative_pnl"
                    stroke="#00d4aa"
                    strokeWidth={2}
                    fill="url(#pnlFill)"
                    dot={false}
                    isAnimationActive={false}
                    name="累計 PnL %"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="page-subtitle" style={{ opacity: 0.75, padding: "8px 0" }}>
                區間內尚無已平倉加總資料，無法繪製曲線。
              </div>
            )}
          </ChartCard>

          <ChartCard title="勝率分布（命中目標 vs 觸發停損）">
            {hasPie ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={78}
                    paddingAngle={2}
                    label={({ name, value }) => `${name}: ${value}`}
                    isAnimationActive={false}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="page-subtitle" style={{ opacity: 0.75, padding: "8px 0" }}>
                區間內尚無「命中目標／觸發停損」筆數，無法繪製甜甜圈。
              </div>
            )}
          </ChartCard>
        </>
      )}

      {mError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          指標歷史載入失敗：{mError.message}（下方 macro 圖表略過）
        </div>
      )}

      {mLoading && !mError && (
        <div className="loading" style={{ padding: "16px", marginBottom: 8 }}>
          載入指標歷史…
        </div>
      )}

      {!hasMetrics && !mLoading && !mError && (
        <div className="page-subtitle" style={{ marginBottom: 14, opacity: 0.75 }}>
          尚無指標歷史序列（macro 圖表略過）。
        </div>
      )}

      {hasMetrics && (
        <>
          <ChartCard title="ICE DXY 美元指數">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} width={36} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line
                  type="monotone"
                  dataKey="dxy"
                  stroke="#00d4aa"
                  dot={false}
                  strokeWidth={2}
                  name="DXY"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="BTC ETF 資金流（億）">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} width={36} />
                <Tooltip contentStyle={tooltipStyle} />
                <ReferenceLine y={0} stroke="var(--border)" />
                <Bar
                  dataKey="etf_flow_millions"
                  name="ETF流"
                  fill="#6366f1"
                  radius={[2, 2, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="MVRV Z-Score">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} width={36} />
                <Tooltip contentStyle={tooltipStyle} />
                <ReferenceLine y={7} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "過熱", fill: "#ef4444", fontSize: 10 }} />
                <ReferenceLine y={0} stroke="var(--border)" />
                <Line
                  type="monotone"
                  dataKey="mvrv_z_score"
                  stroke="#f59e0b"
                  dot={false}
                  strokeWidth={2}
                  name="MVRV Z"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="風險評分 / 5">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 5]} width={28} />
                <Tooltip contentStyle={tooltipStyle} />
                <ReferenceLine y={3.5} stroke="#ef4444" strokeDasharray="4 2" />
                <ReferenceLine y={2.5} stroke="#f59e0b" strokeDasharray="4 2" />
                <Line
                  type="monotone"
                  dataKey="avg_risk_score"
                  stroke="#10b981"
                  dot={false}
                  strokeWidth={2}
                  name="風險評分"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {data.some((r) => r.sentiment_score != null) && (
            <ChartCard title="情緒分數">
              <ResponsiveContainer width="100%" height={140}>
                <LineChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} domain={[-1, 1]} width={28} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine y={0} stroke="var(--border)" />
                  <Line
                    type="monotone"
                    dataKey="sentiment_score"
                    stroke="#a78bfa"
                    dot={false}
                    strokeWidth={2}
                    name="情緒"
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          )}
        </>
      )}
    </>
  );
}
