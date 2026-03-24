import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useMetricsHistory } from "../hooks/useApi";

const PERIODS = [
  { label: "30d", days: 30 },
  { label: "60d", days: 60 },
  { label: "90d", days: 90 },
];

function fmt(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" });
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
  const { data, isLoading, error } = useMetricsHistory(days);

  if (isLoading) return <div className="loading">載入圖表資料…</div>;
  if (error)     return <div className="error-msg">載入失敗：{error.message}</div>;
  if (!data?.length) return <div className="loading">尚無歷史數據</div>;

  const rows = data.map((r) => ({ ...r, label: fmt(r.timestamp) }));

  return (
    <>
      <div className="page-header">
        <div className="page-title">指標圖表</div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {PERIODS.map(({ label, days: d }) => (
          <button
            key={d}
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
  );
}
