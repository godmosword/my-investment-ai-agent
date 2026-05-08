import { useMetricsLatest } from "../../../hooks/useApi";

const SECTORS = [
  { id: "ai_semi",   label: "AI 半導體",  symbols: ["NVDA", "AMD", "INTC"],  baseScore: 88 },
  { id: "cloud",     label: "雲端運算",   symbols: ["MSFT", "GOOGL", "AMZN"], baseScore: 75 },
  { id: "fintech",   label: "金融科技",   symbols: ["SQ", "PYPL", "V"],       baseScore: 62 },
  { id: "crypto",    label: "數位資產",   symbols: ["BTC", "ETH", "SOL"],     baseScore: 80 },
  { id: "consumer",  label: "消費電子",   symbols: ["AAPL", "SONY"],          baseScore: 55 },
  { id: "defense",   label: "國防航太",   symbols: ["LMT", "RTX"],            baseScore: 68 },
  { id: "biotech",   label: "生技醫療",   symbols: ["LLY", "NVO"],            baseScore: 70 },
  { id: "energy",    label: "能源",       symbols: ["XOM", "CVX"],            baseScore: 48 },
];

function adjustScore(base, metrics) {
  if (!metrics) return base;
  const risk = metrics.avg_risk_score ?? 2.5;
  const bias = (2.5 - risk) * 4;
  return Math.max(10, Math.min(98, Math.round(base + bias)));
}

function scoreColor(score) {
  if (score >= 75) return { bg: "rgba(52,211,153,0.15)", border: "rgba(52,211,153,0.35)", text: "var(--green)" };
  if (score >= 55) return { bg: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.3)", text: "var(--yellow)" };
  return { bg: "rgba(248,113,113,0.12)", border: "rgba(248,113,113,0.3)", text: "var(--red)" };
}

function SectorCard({ sector, score }) {
  const col = scoreColor(score);
  return (
    <div
      className="card"
      style={{
        background: col.bg,
        borderColor: col.border,
        padding: "14px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{sector.label}</div>
          <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>
            {sector.symbols.join(" · ")}
          </div>
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: col.text,
            letterSpacing: "-0.03em",
            lineHeight: 1,
          }}
        >
          {score}
        </div>
      </div>
      {/* Score bar */}
      <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div
          style={{
            width: `${score}%`,
            height: "100%",
            background: col.text,
            borderRadius: 2,
            transition: "width 0.5s ease",
          }}
        />
      </div>
      <div style={{ fontSize: 10, color: col.text, fontWeight: 600 }}>
        {score >= 75 ? "強勢" : score >= 55 ? "中性" : "弱勢"}
      </div>
    </div>
  );
}

export default function IndustriesHome() {
  const { data: metrics, isLoading, error } = useMetricsLatest();

  const sectors = SECTORS.map((s) => ({
    ...s,
    score: adjustScore(s.baseScore, metrics),
  })).sort((a, b) => b.score - a.score);

  return (
    <>
      <div className="page-header">
        <div className="page-title">產業趨勢</div>
        <div className="page-subtitle">板塊相對強度（依 BigQuery 風險評分調整）</div>
      </div>

      {isLoading && <div className="loading" style={{ padding: "20px 0" }}>載入指標中…</div>}
      {error && !isLoading && (
        <div className="error-msg" style={{ marginBottom: 12 }}>
          無法載入即時風險評分：<code>{error.message}</code>
          <span style={{ display: "block", marginTop: 6, fontSize: 12, opacity: 0.9 }}>
            以下為板塊基準分（未套用市場偏差）。
          </span>
        </div>
      )}

      {!isLoading && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
            gap: 10,
            marginBottom: 16,
          }}
        >
          {sectors.map((s) => (
            <SectorCard key={s.id} sector={s} score={s.score} />
          ))}
        </div>
      )}

      <div className="card" style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
        <div className="card-title">評分說明</div>
        <p>
          評分由各板塊基準分 × 市場 Risk Score 偏差動態調整。
          基準分源自量化動能、盈利趨勢與情緒加權（研發中）。
          詳細板塊輪動資料請見 Streamlit 戰情室或當日日報。
        </p>
      </div>
    </>
  );
}
