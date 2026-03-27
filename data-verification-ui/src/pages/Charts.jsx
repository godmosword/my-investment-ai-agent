import { useState, useMemo } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { useMetricsHistory, useTradesPerformance } from "../hooks/useApi";

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

export default function Charts() {
  const [days, setDays] = useState(30);
  const { data, isLoading: mLoading, error: mError } = useMetricsHistory(days);
  const { data: perf, isLoading: pLoading, error: pError } = useTradesPerformance(days);

  const equityRows = useMemo(() => {
    const curve = perf?.equity_curve;
    if (!Array.isArray(curve) || !curve.length) return [];
    return curve.map((row) => ({
      ...row,
      label: fmtEquityDate(row.date),
      cumulative_pnl: row.cumulative_pnl != null ? Number(row.cumulative_pnl) : null,
    }));
  }, [perf]);

  const pieData = useMemo(() => {
    const wins = Number(perf?.wins) || 0;
    const losses = Number(perf?.losses) || 0;
    const out = [];
    if (wins > 0) out.push({ name: "命中目標", value: wins, fill: "#10b981" });
    if (losses > 0) out.push({ name: "觸發停損", value: losses, fill: "#ef4444" });
    return out;
  }, [perf]);

  if (mLoading && pLoading) {
    return <div className="loading">載入圖表資料…</div>;
  }

  const hasMetrics = !mError && Array.isArray(data) && data.length > 0;
  const rows = hasMetrics ? data.map((r) => ({ ...r, label: fmt(r.timestamp) })) : [];

  return (
    <>
      <div className="page-header">
        <div className="page-title">指標圖表</div>
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

      {/* ── 績效白盒（Recharts：淨值曲線 + 勝率甜甜圈）────────────────── */}
      {pLoading && (
        <div className="loading" style={{ marginBottom: 12 }}>
          載入交易績效…
        </div>
      )}
      {pError && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          交易績效載入失敗：{pError.message}
        </div>
      )}
      {!pLoading && !pError && perf && (
        <>
          <ChartCard title="資產淨值曲線（累計 PnL %，依平倉日）">
            {equityRows.length ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={equityRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} width={40} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${Number(v).toFixed(2)}%`, "累計"]} />
                  <ReferenceLine y={0} stroke="var(--border)" />
                  <Line
                    type="monotone"
                    dataKey="cumulative_pnl"
                    stroke="#00d4aa"
                    dot={false}
                    strokeWidth={2}
                    name="累計 PnL %"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="page-subtitle" style={{ opacity: 0.75, padding: "8px 0" }}>
                區間內尚無已平倉建議，無法繪製淨值曲線。
              </div>
            )}
          </ChartCard>

          <ChartCard title="勝率分布（命中目標 vs 觸發停損）">
            {pieData.length ? (
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
          指標歷史載入失敗：{mError.message}
        </div>
      )}

      {!hasMetrics && !mLoading && (
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
                <Line type="monotone" dataKey="dxy" stroke="#00d4aa" dot={false} strokeWidth={2} name="DXY" />
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
                <Line type="monotone" dataKey="mvrv_z_score" stroke="#f59e0b" dot={false} strokeWidth={2} name="MVRV Z" />
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
                <Line type="monotone" dataKey="avg_risk_score" stroke="#10b981" dot={false} strokeWidth={2} name="風險評分" />
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
                  <Line type="monotone" dataKey="sentiment_score" stroke="#a78bfa" dot={false} strokeWidth={2} name="情緒" />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          )}
        </>
      )}
    </>
  );
}
