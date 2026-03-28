/**
 * 「今日戰情室」示範資料：無後端／BigQuery 或 API 全失敗時仍可預覽 UI。
 * 啟用：VITE_GLASSBOX_MOCK=1，或在 Today 偵測 metrics+report+positions 皆錯誤時自動套用。
 */
export function useGlassboxDemoMode() {
  return import.meta.env.VITE_GLASSBOX_MOCK === "1";
}

const nowIso = () => new Date().toISOString();

export const MOCK_METRICS_LATEST = {
  timestamp: nowIso(),
  dxy: 104.28,
  etf_flow_millions: 2.35,
  avg_risk_score: 3.2,
  mvrv_z_score: 1.85,
  sentiment_score: 0.12,
  sopr: 1.0082,
  exchange_netflow: -420.5,
  regime_score: 2.8,
  grok_summary:
    "【示範】BTC 資金費率中性，ETF 連日淨流入；山寨季敘事仍依賴 ETH 強度與穩定幣供給。以下為 Glassbox 預覽文案，非即時管線輸出。",
  gpt_summary:
    "【示範】AI 資料中心電力與 GPU 供應鏈仍是主軸；留意利率曲線與雲端 CapEx 指引。",
  delta_dxy: 0.08,
  delta_etf_flow_millions: 0.42,
  delta_avg_risk_score: -0.15,
  delta_mvrv_z_score: 0.05,
  delta_sentiment_score: 0.02,
  delta_sopr: 0.0004,
  delta_exchange_netflow: -12.3,
  delta_regime_score: 0.1,
};

const MOCK_RECOMMENDATIONS_OPEN = [
  {
    asset: "BTC",
    direction: "LONG",
    category: "CRYPTO",
    status: "OPEN",
    position_pct: 5.0,
    pnl_pct: 1.35,
    entry_price: 98500,
    target_price: 102800,
    stop_price: 94800,
    confidence: 3,
    rr_ratio: 2.1,
    timeframe: "swing",
    trigger: "現貨 ETF 淨流入連續為正，且週線收在 20 均線之上；鏈上交易所淨流出延續。",
    invalidation: "週收盤跌破 92k 且三日內無法收回；或單日跌幅 >6% 無下影線反彈。",
    narrative:
      "宏觀流動性邊際改善，BTC 作為風險資產錨點；部位控制在總權益 5% 內，避免與高 beta 山寨重疊曝險。",
  },
  {
    asset: "NVDA",
    direction: "LONG",
    category: "EQUITY",
    status: "OPEN",
    position_pct: 4.2,
    pnl_pct: 2.08,
    entry_price: 128.5,
    target_price: 142.0,
    stop_price: 118.0,
    confidence: 4,
    rr_ratio: 1.8,
    timeframe: "swing",
    trigger: "財報後量能確認 + OpenRouter 動能榜維持前十；RSI 從超賣區重新站上 50。",
    invalidation: "收盤跌破 20 日均線且三日內無法收回；或單日跌幅 >5% 無反彈。",
    narrative:
      "AI CapEx 週期仍向上，NVDA 為算力定價錨；若殖利率曲線陡峭化則降倉而非加碼。",
  },
  {
    asset: "ETH",
    direction: "LONG",
    category: "CRYPTO",
    status: "OPEN",
    position_pct: 3.5,
    pnl_pct: -0.42,
    entry_price: 3450,
    target_price: 3800,
    stop_price: 3180,
    confidence: 2,
    rr_ratio: 1.5,
    timeframe: "short",
    trigger: "L2 手續費與活躍地址回升，且 BTC 波動率回落後 ETH/BTC 比值修復。",
    invalidation: "跌破 3.1k 並伴隨現貨負溢價擴大。",
    narrative: "β 較高，僅在 BTC 趨勢未破前提下持有；與 BTC 部位合計勿超風險預算。",
  },
];

/** 與 mock 報告內 QSREC 一致，供 OPEN 筆數／紅綠燈對齊 */
export const MOCK_OPEN_POSITIONS = MOCK_RECOMMENDATIONS_OPEN;

/** @param {string} reportDate YYYY-MM-DD */
export function mockReportForDate(reportDate) {
  return {
    report_date: reportDate,
    timestamp: nowIso(),
    recommendations: [...MOCK_RECOMMENDATIONS_OPEN],
  };
}
