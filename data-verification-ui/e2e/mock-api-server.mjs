/**
 * Minimal mock API for Playwright (Bloomberg §6 cross-route price alignment).
 * BTC：預設 aligned；`?e2e_btc_misaligned=1` → misaligned；`?e2e_btc_alignment_na=1` → aligned=null。
 * SPY／NVDA：刻意 misaligned 供 Terminal 警告 E2E。
 */
import http from "node:http";

const PORT = Number(process.env.E2E_MOCK_API_PORT || "9999");
const BTC_LAST = 50000.125;
const SPY_OHLC_LAST = 600;
const SPY_QUOTE_LAST = 610.25;
const SPY_REL_DIFF = Math.abs(SPY_QUOTE_LAST - SPY_OHLC_LAST) / SPY_OHLC_LAST;

/** 模擬「儀表 KPI（BQ）≠ 圖表 OHLC 尾端 vs /quote」敘述：snapshot 仍標 source=bigquery，但 OHLC/quote 數值刻意分歧（Bloomberg §6 UI 迴歸）。 */
const NVDA_OHLC_LAST = 880;
const NVDA_QUOTE_LAST = 900.125;
const NVDA_REL_DIFF = Math.abs(NVDA_QUOTE_LAST - NVDA_OHLC_LAST) / NVDA_OHLC_LAST;

/** Phase 2 HUD: after POST /api/run-crew, status is ``running`` briefly (same browser clock). */
let mockCrewLastStartMs = 0;

function enrichAlignment(align) {
  return {
    ...align,
    ohlc_source: "yfinance",
    quote_source: "yfinance",
    daily_metrics_source: "bigquery",
    routes: {
      ohlc: "fetch_symbol_ohlc → price_series[-1].close",
      quote: "fetch_symbol_quote → last",
    },
    e2e_mock_cross_route: true,
  };
}

function baseSnapshot(symbol, lastClose, priceAlignment) {
  return {
    symbol,
    as_of: "2026-04-14T00:00:00+00:00",
    source: "bigquery",
    latest_metrics: {
      timestamp: "2026-04-14T00:00:00+00:00",
      dxy: 100,
      etf_flow_millions: 1,
      avg_risk_score: 2.5,
      mvrv_z_score: 1,
      sentiment_score: 0.1,
      sopr: 1,
      exchange_netflow: -1,
      regime_score: 2,
    },
    history: [],
    price_series: [
      { time: "2026-04-12", open: 1, high: 2, low: 0.5, close: lastClose * 0.98 },
      { time: "2026-04-13", open: 1, high: 2, low: 0.5, close: lastClose * 0.99 },
      { time: "2026-04-14", open: 1, high: 2, low: 0.5, close: lastClose },
    ],
    event_markers: [],
    recommendations:
      symbol === "BTC"
        ? []
        : [
            {
              report_date: "2026-04-14",
              direction: "LONG",
              status: "OPEN",
              entry_price: 1,
              target_price: 2,
              stop_price: 0.5,
            },
          ],
    report_links:
      symbol === "BTC"
        ? []
        : [{ report_date: "2026-04-14", href: "/report/2026-04-14", api_href: "/api/reports/2026-04-14" }],
    data_provenance: {
      ohlc: { source: "yfinance", as_of: "2026-04-14", interval: "1d", underlying_symbol: `${symbol}-USD` },
      daily_metrics: { source: "bigquery", table_id: "e2e.mock", as_of: "2026-04-14T00:00:00+00:00" },
      recommendations: { source: "bigquery", table_id: "e2e.mock", query_window_days: 30, as_of: "2026-04-14T00:00:00+00:00" },
      price_alignment: {
        note: "e2e mock",
        ohlc_vs_quote: priceAlignment,
      },
    },
    price_alignment: enrichAlignment(priceAlignment),
  };
}

const btcAligned = {
  ohlc_last_close: BTC_LAST,
  quote_last: BTC_LAST,
  abs_diff: 0,
  rel_diff: 0,
  aligned: true,
  quote_error: null,
};

const BTC_OHLC_LAST_MIS = 50000;
const BTC_QUOTE_LAST_MIS = 50150.25;
const btcMisaligned = {
  ohlc_last_close: BTC_OHLC_LAST_MIS,
  quote_last: BTC_QUOTE_LAST_MIS,
  abs_diff: BTC_QUOTE_LAST_MIS - BTC_OHLC_LAST_MIS,
  rel_diff: Math.abs(BTC_QUOTE_LAST_MIS - BTC_OHLC_LAST_MIS) / BTC_OHLC_LAST_MIS,
  aligned: false,
  quote_error: null,
};

const btcAlignmentNa = {
  ohlc_last_close: BTC_LAST,
  quote_last: BTC_LAST,
  abs_diff: null,
  rel_diff: null,
  aligned: null,
  quote_error: "backend_unconfirmed",
};

const spyMisaligned = {
  ohlc_last_close: SPY_OHLC_LAST,
  quote_last: SPY_QUOTE_LAST,
  abs_diff: SPY_QUOTE_LAST - SPY_OHLC_LAST,
  rel_diff: SPY_REL_DIFF,
  aligned: false,
  quote_error: null,
};

const nvdaMisaligned = {
  ohlc_last_close: NVDA_OHLC_LAST,
  quote_last: NVDA_QUOTE_LAST,
  abs_diff: NVDA_QUOTE_LAST - NVDA_OHLC_LAST,
  rel_diff: NVDA_REL_DIFF,
  aligned: false,
  quote_error: null,
  e2e_override: true,
};

const macroSnapshotBody = {
  as_of: "2026-05-13T00:00:00Z",
  cache_ttl_seconds: 60,
  cached: false,
  indicator_order: [
    "yields_10y",
    "spread_2s10s",
    "dxy",
    "vix",
    "btc",
    "soxx_spy_ratio",
    "ai_momentum",
    "next_fed_cpi",
  ],
  indicators: {
    yields_10y: {
      id: "yields_10y",
      label: "10Y Yield",
      value: 4.62,
      display: "4.62",
      unit: "%",
      change_1d: 1.1,
      change_5d: 3.2,
      change_unit: "%",
      spark: [4.42, 4.45, 4.48, 4.5, 4.55, 4.59, 4.62],
      source: "yfinance:^TNX",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    spread_2s10s: {
      id: "spread_2s10s",
      label: "2s10s Spread",
      value: 12.5,
      display: "+12.5 bp",
      unit: "bp",
      change_1d: 2.1,
      change_5d: 6.4,
      change_unit: "bp",
      spark: [-2, 0, 3, 5, 8, 10, 12.5],
      source: "yfinance:^TNX/2YY=F",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    dxy: {
      id: "dxy",
      label: "DXY",
      value: 103.2,
      display: "103.20",
      unit: "index",
      change_1d: -0.2,
      change_5d: -0.8,
      change_unit: "%",
      spark: [104.1, 103.9, 103.8, 103.5, 103.4, 103.3, 103.2],
      source: "yfinance:DX-Y.NYB",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    vix: {
      id: "vix",
      label: "VIX",
      value: 17.8,
      display: "17.80",
      unit: "index",
      change_1d: -1.4,
      change_5d: -5.5,
      change_unit: "%",
      spark: [20.5, 19.8, 19.4, 18.9, 18.3, 18.0, 17.8],
      source: "yfinance:^VIX",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    btc: {
      id: "btc",
      label: "BTC",
      value: 50000.125,
      display: "50,000.13",
      unit: "USD",
      change_1d: 1.2,
      change_5d: 4.8,
      change_unit: "%",
      spark: [47800, 48200, 48900, 49300, 49700, 49900, 50000.125],
      source: "yfinance:BTC-USD",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    soxx_spy_ratio: {
      id: "soxx_spy_ratio",
      label: "SOXX / SPY",
      value: 0.418,
      display: "0.418",
      unit: "ratio",
      change_1d: 0.4,
      change_5d: 1.8,
      change_unit: "%",
      spark: [0.408, 0.41, 0.412, 0.414, 0.416, 0.417, 0.418],
      source: "yfinance:SOXX/SPY",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    ai_momentum: {
      id: "ai_momentum",
      label: "AI Momentum",
      value: 106.4,
      display: "106.4",
      unit: "index",
      change_1d: 0.8,
      change_5d: 3.1,
      change_unit: "%",
      spark: [100, 101.2, 102.8, 103.4, 104.9, 105.5, 106.4],
      source: "yfinance:NVDA/AMD/AVGO/MSFT/AAPL/SMH",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
    next_fed_cpi: {
      id: "next_fed_cpi",
      label: "Next Fed / CPI",
      value: 2,
      display: "2026-05-15 · US CPI",
      unit: "days",
      change_1d: null,
      change_5d: null,
      change_unit: "days",
      spark: [],
      source: "financialmodelingprep",
      as_of: "2026-05-13T00:00:00Z",
      error: null,
    },
  },
  catalysts: [
    {
      date: "2026-05-15",
      name: "US CPI",
      importance: "high",
      estimate: "0.3%",
      previous: "0.2%",
      source: "financialmodelingprep",
    },
  ],
  regime: {
    score: 4,
    label: "risk_on",
    drivers: [
      { name: "VIX", score: 1, note: "17.8" },
      { name: "2s10s", score: 0, note: "+12.5bp" },
      { name: "BTC 5D", score: 1, note: "+4.8%" },
      { name: "AI 5D", score: 1, note: "+3.1%" },
      { name: "DXY 5D", score: 1, note: "-0.8%" },
    ],
  },
};

const newsItems = [
  {
    id: "e2e-ai-chip",
    title: "AI 半導體供應鏈拉高資本支出",
    headline: "AI 半導體供應鏈拉高資本支出",
    summary: "雲端 capex 仍是 HBM 與先進封裝的主要推力。",
    gemini_take: "雲端 capex 仍是 HBM 與先進封裝的主要推力。",
    source_domain: "semianalysis.com",
    source_url: "https://semianalysis.com/e2e-ai-chip",
    published_at: "2026-05-13T09:30:00Z",
    date: "2026-05-13",
    tags: ["AI", "半導體"],
    pillar: "半導體",
    pillar_key: "semiconductor",
    confidence: 0.82,
    body: "供應鏈瓶頸仍集中在 HBM、CoWoS 與先進封裝排程，對 NVDA/TSM 的訂單能見度形成支撐。",
    deep_brief: "供應鏈瓶頸仍集中在 HBM、CoWoS 與先進封裝排程，對 NVDA/TSM 的訂單能見度形成支撐。",
    commentary_zh: "供應鏈瓶頸仍集中在 HBM、CoWoS 與先進封裝；NVDA／TSM 訂單能見度短期偏穩。",
    commentary_en: "Supply chain bottlenecks remain centered on HBM, CoWoS, and advanced packaging; NVDA/TSM order visibility looks stable near-term.",
    reading_minutes: 4,
    thesis_breakdown: ["HBM 需求偏強", "先進封裝排程仍緊", "雲端 capex 沒有快速下修"],
    tickers: ["NVDA", "TSM"],
  },
  {
    id: "e2e-crypto-etf",
    title: "Bitcoin ETF 資金流回溫",
    headline: "Bitcoin ETF 資金流回溫",
    summary: "ETF flow 重新回到正值，BTC 風險偏好改善。",
    gemini_take: "ETF flow 重新回到正值，BTC 風險偏好改善。",
    source_domain: "cointelegraph.com",
    source_url: "https://cointelegraph.com/e2e-bitcoin-etf",
    published_at: "2026-05-13T09:00:00Z",
    date: "2026-05-13",
    tags: ["Crypto", "BTC"],
    pillar: "crypto",
    pillar_key: "crypto",
    confidence: 0.71,
    body: "Bitcoin ETF 資金流回溫，使 BTC 現貨買盤重新成為風險偏好的觀察窗口。",
    deep_brief: "Bitcoin ETF 資金流回溫，使 BTC 現貨買盤重新成為風險偏好的觀察窗口。",
    reading_minutes: 3,
    thesis_breakdown: ["ETF flow 轉正", "DXY 回落有利高 beta 資產"],
    tickers: ["BTC"],
  },
  {
    id: "e2e-macro-dollar",
    title: "美元回落支撐科技股風險偏好",
    headline: "美元回落支撐科技股風險偏好",
    summary: "DXY 走弱降低長久期科技股的估值壓力。",
    gemini_take: "DXY 走弱降低長久期科技股的估值壓力。",
    source_domain: "bloomberg.com",
    source_url: "https://bloomberg.com/e2e-macro-dollar",
    published_at: "2026-05-13T08:00:00Z",
    date: "2026-05-13",
    tags: ["宏觀"],
    pillar: "宏觀",
    confidence: 0.64,
  },
];

const newsThemes = [
  { id: "AI", label: "AI", count: 1 },
  { id: "semis", label: "半導體", count: 1 },
  { id: "crypto", label: "Crypto", count: 1 },
  { id: "macro", label: "宏觀", count: 1 },
];

function newsItemMatchesPillar(item, pillar) {
  if (!pillar) return true;
  const wanted = pillar === "semiconductor" ? ["semiconductor", "semis", "半導體", "hbm", "chip"] : [pillar];
  const text = [item.pillar_key, item.pillar, item.headline, item.summary, ...(item.tags || [])]
    .join(" ")
    .toLowerCase();
  return wanted.some((term) => text.includes(term.toLowerCase()));
}

function newsDeepListBody(pillar, limit) {
  return {
    pillar: pillar || null,
    limit,
    items: newsItems.filter((item) => item.deep_brief && newsItemMatchesPillar(item, pillar)).slice(0, limit),
    source: "firestore:tech_pulse_memory_items",
    available: true,
  };
}

function newsDeepBody(id) {
  const item = newsItems.find((row) => row.id === id) || newsItems[0];
  return {
    ...item,
    deep_brief: "供應鏈瓶頸仍集中在 HBM、CoWoS 與先進封裝排程，對 NVDA/TSM 的訂單能見度形成支撐。",
    thesis_breakdown: ["HBM 需求偏強", "先進封裝排程仍緊", "雲端 capex 沒有快速下修"],
    tickers: ["NVDA", "TSM"],
  };
}

const trackRecordRecords = [
  {
    signal_id: "ai-nvda-long-1",
    asset: "NVDA",
    direction: "LONG",
    category: "AI",
    status: "PAPER_CLOSED",
    opened_at: "2026-05-10T00:00:00Z",
    closed_at: "2026-05-11T00:00:00Z",
    entry_price: 100,
    exit_price: 112,
    return_pct: 12,
    outcome: "win",
    thesis_one_liner: "AI demand",
    source: "execution_intents.jsonl",
    source_id: "ai-nvda-long-1",
    tags: ["AI", "NVDA", "LONG", "WIN"],
  },
  {
    signal_id: "crypto-btc-short-1",
    asset: "BTC",
    direction: "SHORT",
    category: "CRYPTO",
    status: "PAPER_CLOSED",
    opened_at: "2026-05-10T00:00:00Z",
    closed_at: "2026-05-12T00:00:00Z",
    entry_price: 50000,
    exit_price: 47500,
    return_pct: 5,
    outcome: "win",
    thesis_one_liner: "Macro hedge",
    source: "execution_intents.jsonl",
    source_id: "crypto-btc-short-1",
    tags: ["CRYPTO", "BTC", "SHORT", "WIN"],
  },
  {
    signal_id: "ai-msft-long-1",
    asset: "MSFT",
    direction: "LONG",
    category: "AI",
    status: "PAPER_CLOSED",
    opened_at: "2026-05-10T00:00:00Z",
    closed_at: "2026-05-13T00:00:00Z",
    entry_price: 200,
    exit_price: 190,
    return_pct: -5,
    outcome: "loss",
    thesis_one_liner: "Cloud reset",
    source: "execution_intents.jsonl",
    source_id: "ai-msft-long-1",
    tags: ["AI", "MSFT", "LONG", "LOSS"],
  },
];

function trackRecordSummary(records = trackRecordRecords) {
  const total = records.length;
  const wins = records.filter((row) => row.return_pct > 0).length;
  const losses = records.filter((row) => row.return_pct < 0).length;
  const avg = total ? records.reduce((sum, row) => sum + row.return_pct, 0) / total : 0;
  let equity = 1;
  const equity_curve = records
    .slice()
    .sort((a, b) => String(a.closed_at).localeCompare(String(b.closed_at)))
    .map((row) => {
      equity *= 1 + row.return_pct / 100;
      return { signal_id: row.signal_id, closed_at: row.closed_at, value: equity, return_pct: row.return_pct };
    });
  return {
    total_closed: total,
    wins,
    losses,
    flats: total - wins - losses,
    hit_rate_pct: total ? (wins / total) * 100 : 0,
    avg_return_pct: avg,
    sharpe: 1.12,
    max_drawdown_pct: -5,
    cumulative_return_pct: (equity - 1) * 100,
    equity_curve,
  };
}

/** Align with `brief_profiles.PROFILES` / `BLOCK_REGISTRY` (minimal mock for structured envelope). */
const PROFILE_BLOCK_IDS = {
  full: [
    "header",
    "exec_summary",
    "previous_recs",
    "market_mode",
    "macro_framework",
    "prediction_markets",
    "crypto_dashboard",
    "crypto_news",
    "crypto_chatter",
    "crypto_trades",
    "ai_bridge",
    "ai_dashboard",
    "ai_news",
    "ai_chatter",
    "ai_trades",
    "current_affairs_roundtable",
    "institutional_view",
    "source_health",
    "qsrec",
  ],
  lite: ["header", "exec_summary", "market_mode", "crypto_trades", "ai_trades", "qsrec"],
  "crypto-only": [
    "header",
    "exec_summary",
    "market_mode",
    "macro_framework",
    "prediction_markets",
    "crypto_dashboard",
    "crypto_news",
    "crypto_chatter",
    "crypto_trades",
    "source_health",
    "qsrec",
  ],
};

const BLOCK_REGISTRY_MOCK = {
  header: { template_subpath: "_header.j2", macro_name: "telegram_header", empty_behavior: "omit_if_empty" },
  exec_summary: { template_subpath: "_exec_summary.j2", macro_name: "telegram_exec_summary", empty_behavior: "omit_if_empty" },
  previous_recs: { template_subpath: "_previous_recs.j2", macro_name: "telegram_previous_recs", empty_behavior: "omit_if_empty" },
  market_mode: { template_subpath: "_market_mode.j2", macro_name: "telegram_market_mode", empty_behavior: "omit_if_empty" },
  macro_framework: { template_subpath: "_macro_framework.j2", macro_name: "telegram_macro_framework", empty_behavior: "omit_if_empty" },
  prediction_markets: { template_subpath: "_prediction_markets.j2", macro_name: "telegram_prediction_markets", empty_behavior: "omit_if_empty" },
  crypto_dashboard: { template_subpath: "_crypto_section.j2", macro_name: "telegram_crypto_section", empty_behavior: "omit_if_empty" },
  crypto_news: { template_subpath: "_crypto_section.j2", macro_name: "telegram_crypto_section", empty_behavior: "omit_if_empty" },
  crypto_chatter: { template_subpath: "_crypto_section.j2", macro_name: "telegram_crypto_section", empty_behavior: "omit_if_empty" },
  crypto_trades: { template_subpath: "_crypto_trades_only.j2", macro_name: "telegram_crypto_trades_only", empty_behavior: "omit_if_empty" },
  ai_bridge: { template_subpath: "_ai_section.j2", macro_name: "telegram_ai_section", empty_behavior: "omit_if_empty" },
  ai_dashboard: { template_subpath: "_ai_section.j2", macro_name: "telegram_ai_section", empty_behavior: "omit_if_empty" },
  ai_news: { template_subpath: "_ai_section.j2", macro_name: "telegram_ai_section", empty_behavior: "omit_if_empty" },
  ai_chatter: { template_subpath: "_ai_section.j2", macro_name: "telegram_ai_section", empty_behavior: "omit_if_empty" },
  ai_trades: { template_subpath: "_ai_trades_only.j2", macro_name: "telegram_ai_trades_only", empty_behavior: "omit_if_empty" },
  current_affairs_roundtable: {
    template_subpath: "_current_affairs_roundtable.j2",
    macro_name: "telegram_current_affairs_roundtable",
    empty_behavior: "omit_if_empty",
  },
  institutional_view: { template_subpath: "_institutional_view.j2", macro_name: "telegram_institutional_view", empty_behavior: "omit_if_empty" },
  source_health: { template_subpath: "_footer_tail.j2", macro_name: "telegram_footer_tail", empty_behavior: "omit_if_empty" },
  qsrec: { template_subpath: "_footer_tail.j2", macro_name: "telegram_footer_tail", empty_behavior: "omit_if_empty" },
};

function validateReportDateParam(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T12:00:00Z`);
  return !Number.isNaN(d.getTime());
}

/** E2E：與 gate-status mock 對齊的最近三日（有別於 legacyReportBody 的 2026-04-14）。 */
const E2E_REPORT_LIST_DATES = ["2026-05-09", "2026-05-08", "2026-05-07"];

function mockReportListRows(limit) {
  const lim = Math.min(Math.max(Number(limit) || 30, 1), 90);
  const n = Math.min(E2E_REPORT_LIST_DATES.length, lim);
  return E2E_REPORT_LIST_DATES.slice(0, n).map((report_date) => ({
    report_date,
    timestamp: `${report_date}T00:00:00Z`,
    dxy: 100,
    etf_flow_millions: 1,
    avg_risk_score: 2.5,
    mvrv_z_score: 1,
    regime_score: 2,
    sentiment_score: 0.1,
    sopr: 1,
    exchange_netflow: -1,
  }));
}

function legacyReportBody(reportDate) {
  return {
    report_date: reportDate,
    timestamp: "2026-04-14T00:00:00Z",
    dxy: 100,
    etf_flow_millions: 1,
    mvrv_z_score: 1,
    avg_risk_score: 2.5,
    sentiment_score: 0.1,
    sopr: 1,
    exchange_netflow: -1,
    grok_summary: "e2e grok",
    gpt_summary: "e2e gpt",
    recommendations: [],
  };
}

/** 最小 DailyBriefReport 形狀：讓 `structured_body_available` 路徑涵蓋 exec_summary／market_mode 專用區塊（與 `structuredBlockContent.js` 對齊）。 */
const E2E_MINIMAL_DAILY_BRIEF_REPORT = {
  crypto: {
    report_title_date: "2026-04-14",
    investment_thesis_one_liner: "e2e structured thesis",
    exec_summary: ["e2e structured bullet"],
    narrative_of_day: "e2e narrative of day",
    market: {
      regime: "risk_on",
      score_suffix: "· e2e score suffix",
      scorecard_lines: ["e2e scorecard line A", "e2e scorecard line B"],
    },
    dashboard: ["DXY 100 · e2e crypto dashboard line", "BTC DOM 55% · mock"],
  },
  ai: {},
  current_affairs_roundtable: {
    topic: "e2e roundtable topic",
    voices: [
      { role: "A", viewpoint: "e2e voice A" },
      { role: "B", viewpoint: "e2e voice B" },
    ],
    unresolved: [],
    consensus: null,
  },
};

function structuredEnvelope(reportDate, profileResolved) {
  const blockIds = PROFILE_BLOCK_IDS[profileResolved];
  const block_registry = {};
  for (const bid of blockIds) {
    if (BLOCK_REGISTRY_MOCK[bid]) block_registry[bid] = { ...BLOCK_REGISTRY_MOCK[bid] };
  }
  const legacy = legacyReportBody(reportDate);
  return {
    report_date: reportDate,
    profile: profileResolved,
    block_ids: blockIds,
    block_registry,
    daily_brief_report: E2E_MINIMAL_DAILY_BRIEF_REPORT,
    structured_body_available: true,
    structured_source: "e2e_mock",
    gate_summary: {
      available: false,
      ok: null,
      issue_count: 0,
      issues: [],
      issues_by_block: {},
      issues_unmapped: [],
      structured_validation: null,
      last_gate_artifact_dir: null,
      last_gate_issues_path: null,
    },
    blocks: [`industry_trends — e2e mock sector view (${reportDate})`],
    metadata: {
      industry_trends: `Semis / AI capex — mock industry_trends line for ${reportDate}.`,
    },
    legacy,
  };
}

const snapshotBtc = baseSnapshot("BTC", BTC_LAST, btcAligned);
const snapshotBtcMisaligned = baseSnapshot("BTC", BTC_OHLC_LAST_MIS, btcMisaligned);
const snapshotBtcAlignmentNa = baseSnapshot("BTC", BTC_LAST, btcAlignmentNa);
const snapshotSpy = baseSnapshot("SPY", SPY_OHLC_LAST, spyMisaligned);
const snapshotNvda = baseSnapshot("NVDA", NVDA_OHLC_LAST, nvdaMisaligned);
snapshotNvda.event_markers = [
  {
    time: "2026-04-14",
    direction: "LONG",
    label: "QSREC OPEN",
    signal_id: "manual-nvda-long-e2e",
    type: "signal",
  },
];
const priceAlerts = [];

function quoteBody(symbol, last) {
  return {
    symbol,
    as_of: "2026-04-14T00:00:00Z",
    source: "yfinance",
    underlying_symbol: `${symbol}-USD`,
    last,
    currency: "USD",
    change_pct_1d: 0.01,
    cached: false,
    data_provenance: {
      price: {
        source: "yfinance",
        as_of: "2026-04-14T00:00:00Z",
        interval: "1d",
        underlying_symbol: `${symbol}-USD`,
      },
    },
  };
}

const metricsBody = {
  timestamp: "2026-04-14T00:00:00Z",
  dxy: 100,
  etf_flow_millions: 1,
  avg_risk_score: 2.5,
  mvrv_z_score: 1,
  sentiment_score: 0.1,
  sopr: 1,
  exchange_netflow: -1,
  regime_score: 2,
  grok_summary: "e2e",
  gpt_summary: "e2e",
};

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, PATCH, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);
  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, PATCH, POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "*",
    });
    res.end();
    return;
  }
  // PATCH /api/execution-intents/{signal_id} — return updated row
  const intentPatchMatch = url.pathname.match(/^\/api\/execution-intents\/([^/]+)$/);
  if (intentPatchMatch && req.method === "PATCH") {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      let body = {};
      try { body = JSON.parse(Buffer.concat(chunks).toString()); } catch { /* ignore */ }
      sendJson(res, 200, {
        signal_id: intentPatchMatch[1],
        created_at: "2026-04-14T00:00:00Z",
        category: "AI",
        regime: "x",
        asset: "SPY",
        direction: "LONG",
        star_rating: 1,
        status: body.status ?? "APPROVED_FOR_PAPER",
        status_updated_at: new Date().toISOString(),
        status_note: body.note ?? "",
        reference_entry_price: body.reference_entry_price ?? null,
        reference_target_price: body.reference_target_price ?? null,
        reference_stop_price: body.reference_stop_price ?? null,
        paper_fill_price: null,
        paper_exit_price: null,
        gate_issue_hints: [],
        quality_score: 85,
        quality_grade: "A",
        quality_reasons: ["high_conviction", "has_entry_target_stop"],
        quality_model: "qsi_signal_quality_v1",
      });
    });
    return;
  }
  if (url.pathname === "/api/execution-intents" && req.method === "POST") {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      let body = {};
      try { body = JSON.parse(Buffer.concat(chunks).toString()); } catch { /* ignore */ }
      sendJson(res, 200, {
        signal_id: `manual-${String(body.asset || "NVDA").toLowerCase()}-long-e2e`,
        created_at: "2026-05-13T00:00:00Z",
        category: String(body.category || "AI").toUpperCase(),
        regime: "",
        asset: String(body.asset || "NVDA").toUpperCase(),
        direction: String(body.direction || "LONG").toUpperCase(),
        star_rating: Number(body.star_rating || 1),
        thesis_one_liner: String(body.thesis_one_liner || ""),
        status: "PENDING_REVIEW",
        status_updated_at: "2026-05-13T00:00:00Z",
        status_note: "",
        reference_entry_price: body.reference_entry_price ?? null,
        reference_target_price: body.reference_target_price ?? null,
        reference_stop_price: body.reference_stop_price ?? null,
        paper_fill_price: null,
        paper_exit_price: null,
        gate_issue_hints: [],
        quality_score: 85,
        quality_grade: "A",
        quality_reasons: ["high_conviction", "has_entry_target_stop"],
        quality_model: "qsi_signal_quality_v1",
      });
    });
    return;
  }
  // POST /api/run-crew
  if (url.pathname === "/api/run-crew" && req.method === "POST") {
    mockCrewLastStartMs = Date.now();
    sendJson(res, 200, { ok: true, status: "started", job_id: "e2emock01" });
    return;
  }
  if (url.pathname === "/api/push/price-alerts" && req.method === "POST") {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      let body = {};
      try { body = JSON.parse(Buffer.concat(chunks).toString()); } catch { /* ignore */ }
      const alert = {
        id: `alert-${priceAlerts.length + 1}`,
        symbol: String(body.symbol || "NVDA").toUpperCase(),
        direction: String(body.direction || "above").toLowerCase(),
        target_price: Number(body.target_price || 900),
        note: String(body.note || ""),
        created_at: "2026-05-13T00:00:00Z",
        last_checked_at: "",
        last_price: null,
        triggered_at: "",
      };
      priceAlerts.push(alert);
      sendJson(res, 200, { alert });
    });
    return;
  }
  if (url.pathname === "/api/push/price-alerts/check" && req.method === "POST") {
    const checked = priceAlerts.map((alert) => ({
      ...alert,
      last_checked_at: "2026-05-13T00:01:00Z",
      last_price: 950,
      triggered_at: alert.direction === "above" && Number(alert.target_price) <= 950 ? "2026-05-13T00:01:00Z" : "",
    }));
    priceAlerts.splice(0, priceAlerts.length, ...checked);
    sendJson(res, 200, {
      checked: checked.length,
      triggered: checked.filter((alert) => alert.triggered_at).length,
      alerts: checked,
      push_results: [],
    });
    return;
  }
  const priceAlertDeleteMatch = url.pathname.match(/^\/api\/push\/price-alerts\/([^/]+)$/);
  if (priceAlertDeleteMatch && req.method === "DELETE") {
    const id = decodeURIComponent(priceAlertDeleteMatch[1]);
    const index = priceAlerts.findIndex((alert) => alert.id === id);
    if (index >= 0) priceAlerts.splice(index, 1);
    sendJson(res, index >= 0 ? 200 : 404, index >= 0 ? { ok: true } : { detail: "not found" });
    return;
  }
  if (req.method !== "GET") {
    sendJson(res, 405, { error: "method" });
    return;
  }
  if (url.pathname === "/api/push/price-alerts/digest") {
    const triggered = priceAlerts.filter((a) => String(a.triggered_at || "").trim());
    const pending = priceAlerts.filter((a) => !String(a.triggered_at || "").trim());
    const symbols = [...new Set(priceAlerts.map((a) => String(a.symbol || "").toUpperCase()))].sort();
    const lastT = triggered.map((a) => String(a.triggered_at)).sort().pop() || null;
    sendJson(res, 200, {
      schema_version: "qsi_price_alert_digest_v1",
      as_of: "2026-05-13T00:00:00Z",
      total: priceAlerts.length,
      pending: pending.length,
      triggered: triggered.length,
      symbols,
      last_triggered_at: lastT,
    });
    return;
  }
  if (url.pathname === "/api/metrics/latest") {
    sendJson(res, 200, metricsBody);
    return;
  }
  if (url.pathname === "/api/macro/snapshot") {
    sendJson(res, 200, macroSnapshotBody);
    return;
  }
  if (url.pathname === "/api/push/price-alerts") {
    sendJson(res, 200, { alerts: priceAlerts });
    return;
  }
  if (url.pathname === "/api/news/digest") {
    const limit = Number(url.searchParams.get("limit") || "20");
    sendJson(res, 200, {
      date: url.searchParams.get("date"),
      limit,
      items: newsItems.slice(0, limit),
      themes: newsThemes,
      source: "firestore:tech_pulse_memory_items",
      available: true,
    });
    return;
  }
  if (url.pathname === "/api/news/themes") {
    sendJson(res, 200, { themes: newsThemes, source: "firestore:tech_pulse_memory_items" });
    return;
  }
  if (url.pathname === "/api/news/deep") {
    const pillar = String(url.searchParams.get("pillar") || "").toLowerCase();
    const limit = Number(url.searchParams.get("limit") || "20");
    sendJson(res, 200, newsDeepListBody(pillar, limit));
    return;
  }
  const newsDeepMatch = url.pathname.match(/^\/api\/news\/deep\/([^/]+)$/);
  if (newsDeepMatch) {
    sendJson(res, 200, newsDeepBody(decodeURIComponent(newsDeepMatch[1])));
    return;
  }
  const snapMatch = url.pathname.match(/^\/api\/symbols\/([^/]+)\/snapshot$/);
  if (snapMatch) {
    const sym = snapMatch[1].toUpperCase();
    if (url.searchParams.get("e2e_snapshot_fail") === "1") {
      sendJson(res, 503, { detail: `snapshot unavailable for ${sym}` });
      return;
    }
    if (sym === "BTC") {
      const mis = url.searchParams.get("e2e_btc_misaligned") === "1";
      const na = url.searchParams.get("e2e_btc_alignment_na") === "1";
      sendJson(res, 200, na ? snapshotBtcAlignmentNa : mis ? snapshotBtcMisaligned : snapshotBtc);
      return;
    }
    if (sym === "SPY") {
      sendJson(res, 200, snapshotSpy);
      return;
    }
    if (sym === "NVDA") {
      sendJson(res, 200, snapshotNvda);
      return;
    }
    sendJson(res, 404, { error: "unknown_symbol" });
    return;
  }
  const quoteMatch = url.pathname.match(/^\/api\/symbols\/([^/]+)\/quote$/);
  if (quoteMatch) {
    const sym = quoteMatch[1].toUpperCase();
    if (url.searchParams.get("e2e_quote_fail") === "1") {
      sendJson(res, 503, { detail: `quote unavailable for ${sym}` });
      return;
    }
    if (sym === "BTC") {
      const mis = url.searchParams.get("e2e_btc_misaligned") === "1";
      sendJson(res, 200, quoteBody("BTC", mis ? BTC_QUOTE_LAST_MIS : BTC_LAST));
      return;
    }
    if (sym === "SPY") {
      sendJson(res, 200, quoteBody("SPY", SPY_QUOTE_LAST));
      return;
    }
    if (sym === "NVDA") {
      sendJson(res, 200, quoteBody("NVDA", NVDA_QUOTE_LAST));
      return;
    }
    sendJson(res, 404, { error: "unknown_symbol" });
    return;
  }
  if (url.pathname === "/api/war-room/latest") {
    sendJson(res, 200, {
      gate_failure: {
        valid: false,
        issue_count: 1,
        issues: ["SPY exposure check failed for SPY leg"],
        written_utc: "2026-04-14T00:00:00Z",
      },
      scratchpad: null,
      execution_intents: [
        {
          signal_id: "e2e-spy-1",
          created_at: "2026-04-14T00:00:00Z",
          category: "AI",
          regime: "x",
          asset: "SPY",
          direction: "LONG",
          star_rating: 1,
          status: "PENDING_REVIEW",
          status_updated_at: "2026-04-14T00:00:00Z",
        },
      ],
    });
    return;
  }
  if (url.pathname.startsWith("/api/execution-intents/allowed-statuses")) {
    sendJson(res, 200, {
      statuses: ["PENDING_REVIEW", "APPROVED_FOR_PAPER"],
      client_patchable: ["PENDING_REVIEW", "APPROVED_FOR_PAPER", "REJECTED", "SUPERSEDED"],
    });
    return;
  }
  if (url.pathname === "/api/execution-intents/gate-index") {
    sendJson(res, 200, {
      schema_version: "qsi_gate_intent_index_v1",
      readme: "e2e mock gate × intent index",
      gate_artifact_present: true,
      gate_issue_preview: ["SPY exposure check failed for SPY leg"],
      gate_issue_count: 1,
      intent_scanned: 1,
      intent_rows_with_hints: 1,
      matches: [
        {
          signal_id: "e2e-spy-1",
          asset: "SPY",
          status: "PENDING_REVIEW",
          hint_count: 1,
          gate_issue_hints: ["SPY exposure check failed for SPY leg"],
        },
      ],
    });
    return;
  }
  if (url.pathname.startsWith("/api/execution-intents")) {
    sendJson(res, 200, [
      {
        signal_id: "e2e-spy-1",
        created_at: "2026-04-14T00:00:00Z",
        category: "AI",
        regime: "x",
        asset: "SPY",
        direction: "LONG",
        star_rating: 1,
        status: "PENDING_REVIEW",
        status_updated_at: "2026-04-14T00:00:00Z",
        gate_issue_hints: ["SPY exposure check failed for SPY leg"],
        quality_score: 25,
        quality_grade: "D",
        quality_reasons: ["base_conviction", "missing_entry", "gate_warning"],
        quality_model: "qsi_signal_quality_v1",
      },
    ]);
    return;
  }
  if (url.pathname === "/api/paper/lifecycle" || url.pathname === "/api/paper/pnl") {
    sendJson(res, 200, {
      as_of: "2026-05-13T00:00:00Z",
      source: "execution_intents.jsonl",
      summary: {
        total: 2,
        active_count: 1,
        closed_count: 1,
        status_counts: { APPROVED_FOR_PAPER: 1, PAPER_CLOSED: 1 },
        wins: 1,
        losses: 0,
        win_rate_pct: 100,
        avg_realized_return_pct: 10,
        avg_unrealized_return_pct: 12,
        best_return_pct: 12,
        worst_return_pct: 10,
        quote_error_count: 0,
        avg_quality_score: 78.5,
        quality_counts: { A: 1, B: 1 },
        avg_return_by_quality: { A: 12, B: 10 },
      },
      rows: [
        {
          signal_id: "e2e-nvda-long-open",
          created_at: "2026-05-12T00:00:00Z",
          status_updated_at: "2026-05-13T00:00:00Z",
          category: "AI",
          asset: "NVDA",
          direction: "LONG",
          star_rating: 2,
          thesis_one_liner: "AI capex impulse",
          status: "APPROVED_FOR_PAPER",
          entry_price: 100,
          mark_price: 112,
          exit_price: null,
          return_pct: 12,
          target_distance_pct: 30,
          stop_distance_pct: 10,
          r_multiple: 3,
          quality_score: 92,
          quality_grade: "A",
          quality_reasons: ["high_conviction", "clear_thesis", "has_entry_target_stop"],
          quality_model: "qsi_signal_quality_v1",
        },
        {
          signal_id: "e2e-btc-short-closed",
          created_at: "2026-05-10T00:00:00Z",
          status_updated_at: "2026-05-11T00:00:00Z",
          category: "CRYPTO",
          asset: "BTC",
          direction: "SHORT",
          star_rating: 1,
          thesis_one_liner: "ETF flow cooled",
          status: "PAPER_CLOSED",
          entry_price: 50,
          mark_price: 45,
          exit_price: 45,
          return_pct: 10,
          target_distance_pct: null,
          stop_distance_pct: null,
          r_multiple: null,
          quality_score: 65,
          quality_grade: "B",
          quality_reasons: ["base_conviction", "clear_thesis", "has_entry"],
          quality_model: "qsi_signal_quality_v1",
        },
      ],
    });
    return;
  }
  if (url.pathname === "/api/paper/transparency-letter") {
    sendJson(res, 200, {
      as_of: "2026-05-13T00:00:00Z",
      month: url.searchParams.get("month") || "2026-05",
      source: "execution_intents.jsonl+portfolio_holdings.jsonl",
      summary: {
        closed_count: 1,
        wins: 1,
        losses: 0,
        win_rate_pct: 100,
        avg_return_pct: 10,
        best_return_pct: 10,
        worst_return_pct: 10,
        avg_quality_score: 65,
        quality_counts: { B: 1 },
        min_publishable_sample: 5,
        publishable: false,
      },
      alignment: {
        portfolio_symbols: ["NVDA"],
        paper_symbols: ["BTC"],
        matched_symbols: [],
        paper_only_symbols: ["BTC"],
        portfolio_only_symbols: ["NVDA"],
      },
      rows: [],
      letter_markdown: "# Paper Transparency Letter — 2026-05\n\nInternal review only.",
    });
    return;
  }
  if (url.pathname === "/api/brief-layouts") {
    sendJson(res, 200, {
      layouts: [
        {
          filename: "example_lite_reorder.yaml",
          path: "config/brief_layouts/example_lite_reorder.yaml",
          applies_to_profile: "lite",
          blocks: ["header", "macro", "crypto", "us_equities"],
          parse_error: null,
        },
      ],
      runtime_hints: {
        brief_layout_file: "config/brief_layouts/example_lite_reorder.yaml",
        brief_dynamic_render: false,
        report_profile: "lite",
      },
    });
    return;
  }
  if (url.pathname === "/api/reports/profile-stats" || url.pathname.startsWith("/api/reports/profile-stats")) {
    const days = Number(url.searchParams.get("days") || "30") || 30;
    sendJson(res, 200, {
      window_days: days,
      total_reports: 0,
      breakdown: [
        { profile: "full", report_count: 0, latest_date: null },
        { profile: "lite", report_count: 0, latest_date: null },
        { profile: "crypto-only", report_count: 0, latest_date: null },
      ],
    });
    return;
  }
  if (url.pathname === "/api/gate-failures" || url.pathname.startsWith("/api/gate-failures")) {
    const days = Number(url.searchParams.get("days") || "7") || 7;
    sendJson(res, 200, {
      days,
      count: 2,
      source: "fixture",
      entries: [
        {
          timestamp: "2026-05-19T02:31:00+00:00",
          attempt: 2,
          blocking_count: 1,
          warning_count: 3,
          issue_count: 4,
          profile: "full",
          used_fallback: false,
          issues_preview: "e2e mock — exec_summary 缺 market_regime",
        },
        {
          timestamp: "2026-05-18T02:44:00+00:00",
          attempt: 1,
          blocking_count: 0,
          warning_count: 2,
          issue_count: 2,
          profile: "lite",
          used_fallback: false,
          issues_preview: "e2e mock — trade_legs direction",
        },
      ],
    });
    return;
  }
  if (url.pathname === "/api/reports/qsrec-stats" || url.pathname.startsWith("/api/reports/qsrec-stats")) {
    const days = Number(url.searchParams.get("days") || "7") || 7;
    sendJson(res, 200, {
      days,
      total_days: 5,
      pass_count: 4,
      degraded_count: 1,
      fail_count: 0,
      pass_rate_pct: 80.0,
      avg_trade_count: 3.2,
    });
    return;
  }
  const gateStatusMatch = url.pathname.match(/^\/api\/reports\/(\d{4}-\d{2}-\d{2})\/gate-status$/);
  if (gateStatusMatch) {
    const d = gateStatusMatch[1];
    const statusByDate = {
      "2026-05-09": { gate_status: "pass", degraded: false, revision_count: 0, final_trade_count: 4 },
      "2026-05-08": { gate_status: "fail", degraded: false, revision_count: 2, final_trade_count: 3 },
      "2026-05-07": { gate_status: "degraded", degraded: true, revision_count: 0, final_trade_count: 2 },
    };
    const row = statusByDate[d];
    if (row) {
      sendJson(res, 200, { run_id: `e2e-${d}`, ...row });
      return;
    }
    sendJson(res, 200, { gate_status: "未審" });
    return;
  }
  const analysisMatch = url.pathname.match(/^\/api\/analysis\/([^/]+)$/);
  if (analysisMatch) {
    const sym = analysisMatch[1].toUpperCase();
    const last = sym === "BTC" ? BTC_LAST : sym === "NVDA" ? 100.5 : 100;
    // 20 OHLC bars; per-bar high-low spread = 2 → ATR(14) ≈ 2.0 (used by PortfolioRiskPanel test)
    const series = [];
    for (let i = 0; i < 20; i += 1) {
      const close = 100 + i * 0.3;
      series.push({
        time: `2026-05-${String(i + 1).padStart(2, "0")}`,
        open: close - 0.1,
        high: close + 1.0,
        low: close - 1.0,
        close,
      });
    }
    const snap =
      sym === "NVDA"
        ? { symbol: sym, source: "e2e_mock", as_of: "2026-04-14T00:00:00+00:00", price_series: series }
        : { symbol: sym, source: "e2e_mock", as_of: "2026-04-14T00:00:00+00:00", price_series: series };
    sendJson(res, 200, {
      symbol: sym,
      quote: { symbol: sym, last, source: "e2e_mock" },
      snapshot: snap,
      snapshot_error: null,
    });
    return;
  }
  const structuredMatch = url.pathname.match(/^\/api\/reports\/(\d{4}-\d{2}-\d{2})\/structured$/);
  if (structuredMatch) {
    const reportDate = structuredMatch[1];
    if (!validateReportDateParam(reportDate)) {
      sendJson(res, 400, { detail: "invalid date" });
      return;
    }
    const rawProfile = (url.searchParams.get("profile") || "full").trim().toLowerCase();
    const normalized =
      rawProfile === "crypto_only" ? "crypto-only" : rawProfile === "cryptoonly" ? "crypto-only" : rawProfile;
    if (!Object.prototype.hasOwnProperty.call(PROFILE_BLOCK_IDS, normalized)) {
      sendJson(res, 400, { detail: `invalid profile: ${rawProfile}` });
      return;
    }
    sendJson(res, 200, structuredEnvelope(reportDate, normalized));
    return;
  }
  const reportsListMatch = url.pathname.match(/^\/api\/reports\/?$/);
  if (reportsListMatch) {
    const lim = Number(url.searchParams.get("limit") || "30") || 30;
    sendJson(res, 200, mockReportListRows(lim));
    return;
  }
  const reportDayMatch = url.pathname.match(/^\/api\/reports\/(\d{4}-\d{2}-\d{2})$/);
  if (reportDayMatch) {
    const d = reportDayMatch[1];
    if (!validateReportDateParam(d)) {
      sendJson(res, 400, { detail: "invalid date" });
      return;
    }
    sendJson(res, 200, legacyReportBody(d));
    return;
  }
  if (url.pathname === "/api/portfolio") {
    sendJson(res, 200, {
      holdings: [
        {
          id: "1",
          symbol: "NVDA",
          shares: 10,
          cost_basis: 500,
          opened_at: "2024-01-01",
          notes: "",
        },
      ],
    });
    return;
  }
  if (url.pathname === "/api/portfolio/pnl") {
    sendJson(res, 200, {
      total_value: 8000,
      total_pnl: 3000,
      total_day_pnl: 120,
      holdings: [
        {
          id: "1",
          symbol: "NVDA",
          shares: 10,
          cost_basis: 500,
          opened_at: "2024-01-01",
          notes: "",
          last_price: 800,
          day_change_pct: 1.5,
          market_value: 8000,
          cost: 5000,
          pnl: 3000,
          pnl_pct: 60,
          day_pnl: 120,
          weight: 100,
        },
      ],
    });
    return;
  }
  if (url.pathname === "/api/track-record/summary") {
    sendJson(res, 200, {
      ...trackRecordSummary(trackRecordRecords),
      source: "execution_intents.jsonl",
      source_row_count: trackRecordRecords.length,
    });
    return;
  }
  if (url.pathname === "/api/track-record/closed") {
    sendJson(res, 200, {
      summary: trackRecordSummary(trackRecordRecords),
      records: trackRecordRecords,
      total: trackRecordRecords.length,
      limit: Number(url.searchParams.get("limit") || "50"),
      offset: Number(url.searchParams.get("offset") || "0"),
      source: "execution_intents.jsonl",
    });
    return;
  }
  if (url.pathname === "/api/track-record/by-tag") {
    const tag = String(url.searchParams.get("tag") || "").toUpperCase();
    const records = trackRecordRecords.filter((row) => row.tags.includes(tag) || row.category === tag || row.outcome.toUpperCase() === tag);
    sendJson(res, 200, {
      summary: trackRecordSummary(records),
      records,
      total: records.length,
      limit: Number(url.searchParams.get("limit") || "50"),
      offset: Number(url.searchParams.get("offset") || "0"),
      source: "execution_intents.jsonl",
      tag,
    });
    return;
  }
  /** M4 aggregate — exact path only (before `/api/positions/open`). */
  if (url.pathname === "/api/positions") {
    sendJson(res, 200, [
      {
        report_date: "2026-04-14",
        asset: "NVDA",
        direction: "LONG",
        status: "OPEN",
        entry_price: 100,
        confidence: 0.7,
      },
    ]);
    return;
  }
  if (url.pathname === "/api/industries/themes" || url.pathname.startsWith("/api/industries/themes")) {
    sendJson(res, 200, {
      themes: [
        { id: "ai-semis", label: "AI 半導體（e2e）", symbols: ["NVDA"], regime_score: 4, risk_level: "medium", thesis: "AI capex impulse" },
        { id: "clean-energy", label: "清潔能源（e2e）", symbols: ["ENPH"], regime_score: 1, risk_level: "medium", thesis: "Policy beta" },
        { id: "financials", label: "金融（e2e）", symbols: ["JPM"], regime_score: -1, risk_level: "low", thesis: "Curve pressure" },
      ],
      rotation: [
        { id: "ai-semis", label: "AI 半導體（e2e）", symbols: ["NVDA"], regime_score: 4, risk_level: "medium" },
        { id: "clean-energy", label: "清潔能源（e2e）", symbols: ["ENPH"], regime_score: 1, risk_level: "medium" },
        { id: "financials", label: "金融（e2e）", symbols: ["JPM"], regime_score: -1, risk_level: "low" },
      ],
      intent_sample_regime: 3,
      intent_count: 2,
      source: "static+execution_intents.jsonl",
    });
    return;
  }
  if (url.pathname === "/api/options/summary") {
    sendJson(res, 200, {
      enabled: true,
      as_of: "2026-06-19T22:30:00Z",
      watchlist: ["MU", "NVDA", "AMD"],
      items: [
        { underlying: "MU", gex: { total_gex: 300000, call_gex: 500000, put_gex: -200000, spot_price: 100, regime: "positive", trade_date: "2026-06-19" }, unusual_count: 2 },
        { underlying: "NVDA", gex: { total_gex: -450000, call_gex: 250000, put_gex: -700000, spot_price: 130, regime: "negative", trade_date: "2026-06-19" }, unusual_count: 1 },
        { underlying: "AMD", gex: null, unusual_count: 0 },
      ],
    });
    return;
  }
  if (url.pathname.startsWith("/api/options/gex/")) {
    const sym = decodeURIComponent(url.pathname.split("/").pop() || "").toUpperCase();
    sendJson(res, 200, {
      enabled: true,
      underlying: sym,
      as_of: "2026-06-19T22:30:00Z",
      gex: { underlying: sym, total_gex: 300000, call_gex: 500000, put_gex: -200000, spot_price: 100, regime: "positive", trade_date: "2026-06-19" },
      history: [
        { trade_date: "2026-06-17", total_gex: 220000, call_gex: 400000, put_gex: -180000, spot_price: 98 },
        { trade_date: "2026-06-18", total_gex: 260000, call_gex: 450000, put_gex: -190000, spot_price: 99 },
        { trade_date: "2026-06-19", total_gex: 300000, call_gex: 500000, put_gex: -200000, spot_price: 100 },
      ],
    });
    return;
  }
  if (url.pathname.startsWith("/api/options/flow/")) {
    const sym = decodeURIComponent(url.pathname.split("/").pop() || "").toUpperCase();
    sendJson(res, 200, {
      enabled: true,
      underlying: sym,
      as_of: "2026-06-19T22:30:00Z",
      signals: [
        { trade_date: "2026-06-19", option_ticker: `O:${sym}260116C00100000`, signal_type: "volume_oi", score: 0.5, premium: null, volume: 5000, open_interest: 1000, rationale: "day_volume 5000 = 5.0x open_interest 1000" },
        { trade_date: "2026-06-19", option_ticker: `O:${sym}260116C00110000`, signal_type: "sweep", score: 0.4, premium: 690000, volume: 300, open_interest: 800, rationale: "sweep across 3 exchanges" },
      ],
    });
    return;
  }
  if (url.pathname === "/api/run-crew/status") {
    const within = mockCrewLastStartMs > 0 && Date.now() - mockCrewLastStartMs < 12_000;
    if (within) {
      sendJson(res, 200, {
        status: "running",
        job_id: "e2emock01",
        started_at: new Date(mockCrewLastStartMs).toISOString(),
        finished_at: null,
        error: null,
      });
      return;
    }
    sendJson(res, 200, { status: "idle", job_id: null, started_at: null, finished_at: null, error: null });
    return;
  }
  if (url.pathname === "/api/macro/onchain") {
    sendJson(res, 200, {
      enabled: true,
      live: false,
      as_of: "2026-05-16",
      cached: false,
      disclaimer: "MOCK FIXTURE — UI scaffold; not real on-chain data.",
      btc_valuation: {
        as_of: "2026-05-16",
        source: "mock",
        note: "Cycle valuation snapshot.",
        items: [
          { metric: "MVRV-Z", value: 1.85, regime: "neutral", note: "" },
          { metric: "Realized Price", value: 38_500, unit: "USD", note: "" },
          { metric: "Spot Price", value: 64_200, unit: "USD", note: "" },
          { metric: "Spot / Realized", value: 1.67, note: "neutral" },
        ],
      },
      exchange_flow: {
        as_of: "2026-05-16",
        enabled: false,
        source: "none",
        reason: "no_free_equivalent",
        note: "CEX netflow has no approved free equivalent.",
        items: [],
      },
      funding_rate: {
        as_of: "2026-05-16",
        source: "mock",
        note: "Annualized perpetual funding.",
        items: [
          { asset: "BTC", venue: "Binance", funding_apr_pct: 6.8 },
          { asset: "ETH", venue: "Binance", funding_apr_pct: 4.2 },
        ],
      },
      live_block_status: { valuation: "mock", exchange_flow: "disabled", funding: "mock" },
    });
    return;
  }
  if (url.pathname === "/api/macro/compute-memory") {
    sendJson(res, 200, {
      enabled: true,
      live: false,
      as_of: "2026-05-16",
      cached: false,
      disclaimer: "MOCK FIXTURE — UI scaffold; not real market data.",
      hbm_dram_spot: {
        as_of: "2026-05-16",
        source: "mock",
        note: "Spot $ per 8-Gb-equivalent contract.",
        items: [
          { product: "HBM3", spec: "8H 16Gb", spot_usd: 9.20, trend_pct: 1.2, note: "" },
          { product: "HBM3e", spec: "12H 24Gb", spot_usd: 14.75, trend_pct: 3.4, note: "" },
          { product: "DDR5", spec: "16Gb DIMM", spot_usd: 4.10, trend_pct: -0.8, note: "" },
        ],
      },
      hyperscaler_capex: {
        as_of: "2026-Q1",
        source: "mock",
        note: "Quarterly capex (USD bn).",
        items: [
          { ticker: "MSFT", quarter: "2026-Q1", capex_b_usd: 22.4, yoy_pct: 35.0, guide_direction: "up" },
          { ticker: "GOOG", quarter: "2026-Q1", capex_b_usd: 17.2, yoy_pct: 28.0, guide_direction: "up" },
          { ticker: "META", quarter: "2026-Q1", capex_b_usd: 12.5, yoy_pct: 40.0, guide_direction: "up" },
        ],
      },
      gpu_spot: {
        as_of: "2026-05-16",
        source: "mock",
        note: "Hourly $ on-demand.",
        items: [
          { sku: "H100 SXM", provider: "MOCK", hourly_usd: 2.49, regions: ["us-east", "eu-west"] },
          { sku: "H200 SXM", provider: "MOCK", hourly_usd: 3.89, regions: ["us-east"] },
          { sku: "B200 HGX", provider: "MOCK", hourly_usd: 5.99, regions: ["us-east"] },
        ],
      },
    });
    return;
  }
  if (url.pathname === "/api/earnings/upcoming") {
    sendJson(res, 200, {
      as_of: "2026-05-16",
      days: 14,
      watchlist_size: 3,
      items: [
        { symbol: "NVDA", pillar: "ai_silicon", next_earnings_date: "2026-05-20", days_until: 4, status: "unknown" },
        { symbol: "MSFT", pillar: "cloud_software", next_earnings_date: "2026-05-22", days_until: 6, status: "unknown" },
        { symbol: "TSM", pillar: "semiconductor", next_earnings_date: "2026-05-27", days_until: 11, status: "unknown" },
      ],
    });
    return;
  }
  if (url.pathname.startsWith("/api/earnings/") && url.pathname.endsWith("/insight")) {
    const parts = url.pathname.split("/");
    const symbol = (parts[3] || "").toUpperCase();
    if (symbol === "NVDA") {
      sendJson(res, 200, {
        enabled: true,
        symbol: "NVDA",
        as_of: "2026-05-01",
        analysis: {
          ticker: "NVDA",
          filing_type: "10-Q",
          answers: { 1: "Datacenter revenue grew 80% YoY driven by Hopper + Blackwell ramp." },
          citations: { 1: [{ excerpt: "MD&A — datacenter segment" }] },
          red_flags: ["Inventory days up 12%"],
        },
      });
    } else {
      sendJson(res, 200, {
        enabled: false,
        symbol,
        reason: "no_filing_scaffold_data",
        hint: "Set DEEP_FILING_ANALYSIS_FILE and append a JSONL row.",
      });
    }
    return;
  }
  if (url.pathname === "/api/scenario/suggestions") {
    sendJson(res, 200, {
      enabled: true,
      as_of: "2026-05-14T00:00:00Z",
      sources: { execution_intents: "EXECUTION_INTENT_STORE", portfolio_holdings: "PORTFOLIO_HOLDINGS_FILE" },
      disclaimer: "e2e mock; internal planning only.",
      portfolio: { positions: 1, concentration_hhi: 1, top_symbols: [{ symbol: "NVDA", weight_pct: 100 }] },
      paper: { active_open_count: 0, active_by_asset: {}, overlap_with_portfolio: [] },
      track_record_summary: { closed_count: 0, win_rate_pct: 0, avg_return_pct: 0 },
      scenarios: [
        {
          id: "defensive",
          label: "Defensive tilt",
          notional_shift_pct: -5,
          rationale_codes: ["HIGH_HHI"],
          notes: "mock",
        },
        { id: "base", label: "Hold structure", notional_shift_pct: 0, rationale_codes: ["NEUTRAL"], notes: "mock" },
        {
          id: "opportunistic",
          label: "Opportunistic trim",
          notional_shift_pct: 0,
          rationale_codes: ["NEUTRAL"],
          notes: "mock",
        },
      ],
      target_hints: [],
    });
    return;
  }
  if (url.pathname === "/api/quant/backtest") {
    const symbol = url.searchParams.get("symbol") ?? "BTC";
    sendJson(res, 200, {
      symbol: symbol.toUpperCase(),
      equity_curve: [
        { date: "day_01", value: 10000 },
        { date: "day_02", value: 10150 },
        { date: "day_03", value: 10080 },
        { date: "day_04", value: 10320 },
      ],
      total_return: 0.032,
      max_drawdown: 0.007,
      sharpe: 4.571,
      trade_count: 3,
      source: "execution_intents.jsonl",
      disclaimer: "e2e mock",
    });
    return;
  }
  if (url.pathname === "/api/quant/signals") {
    sendJson(res, 200, {
      disclaimer: "e2e mock; not investment advice.",
      source: "execution_intents.jsonl",
      count: 2,
      signals: [
        {
          id: "e2e-nvda-filled",
          symbol: "NVDA",
          asset: "NVDA",
          label: "AI capex momentum",
          direction: "long",
          confidence: 1,
          status: "PAPER_FILLED",
          category: "AI",
        },
        {
          id: "e2e-spy-review",
          symbol: "SPY",
          asset: "SPY",
          label: "Index hedge watch",
          direction: "long",
          confidence: 0.5,
          status: "PENDING_REVIEW",
          category: "AI",
        },
      ],
    });
    return;
  }
  if (url.pathname === "/api/positions/open" || url.pathname.startsWith("/api/positions/open")) {
    sendJson(res, 200, []);
    return;
  }
  if (url.pathname.startsWith("/api/trades")) {
    if (url.pathname.includes("performance")) {
      sendJson(res, 200, { stats: {}, equity_curve: [] });
    } else {
      sendJson(res, 200, []);
    }
    return;
  }
  sendJson(res, 404, { error: "not_found", path: url.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  console.error(`e2e mock API listening on http://127.0.0.1:${PORT}`);
});
