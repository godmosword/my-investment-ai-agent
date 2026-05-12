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
    legacy,
  };
}

const snapshotBtc = baseSnapshot("BTC", BTC_LAST, btcAligned);
const snapshotBtcMisaligned = baseSnapshot("BTC", BTC_OHLC_LAST_MIS, btcMisaligned);
const snapshotBtcAlignmentNa = baseSnapshot("BTC", BTC_LAST, btcAlignmentNa);
const snapshotSpy = baseSnapshot("SPY", SPY_OHLC_LAST, spyMisaligned);
const snapshotNvda = baseSnapshot("NVDA", NVDA_OHLC_LAST, nvdaMisaligned);

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
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "*",
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);
  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, PATCH, POST, OPTIONS",
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
      });
    });
    return;
  }
  // POST /api/run-crew
  if (url.pathname === "/api/run-crew" && req.method === "POST") {
    sendJson(res, 200, { ok: true, status: "started", job_id: "e2emock01" });
    return;
  }
  if (req.method !== "GET") {
    sendJson(res, 405, { error: "method" });
    return;
  }
  if (url.pathname === "/api/metrics/latest") {
    sendJson(res, 200, metricsBody);
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
      },
    ]);
    return;
  }
  if (url.pathname === "/api/brief-layouts") {
    sendJson(res, 200, { layouts: [] });
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
    sendJson(res, 200, []);
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
        { id: "ai-semis", label: "AI 半導體（e2e）", symbols: ["NVDA"], regime_score: 4 },
        { id: "clean-energy", label: "清潔能源（e2e）", symbols: ["ENPH"], regime_score: 1 },
        { id: "financials", label: "金融（e2e）", symbols: ["JPM"], regime_score: -1 },
      ],
      intent_sample_regime: 3,
      intent_count: 2,
    });
    return;
  }
  const analysisMatch = url.pathname.match(/^\/api\/analysis\/([^/]+)$/);
  if (analysisMatch) {
    const sym = String(analysisMatch[1] || "").toUpperCase();
    sendJson(res, 200, {
      symbol: sym,
      quote: { symbol: sym, last: 100.5 },
      snapshot: { symbol: sym, source: "e2e_mock", as_of: "2026-04-14T00:00:00+00:00" },
      snapshot_error: null,
    });
    return;
  }
  if (url.pathname === "/api/run-crew/status") {
    sendJson(res, 200, { status: "idle", job_id: null, started_at: null, finished_at: null, error: null });
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
      disclaimer: "e2e mock",
    });
    return;
  }
  if (url.pathname === "/api/quant/signals") {
    sendJson(res, 200, {
      disclaimer: "e2e mock; not investment advice.",
      signals: [{ id: "e2e-neutral", label: "RSI14 band (mock)", direction: "neutral", confidence: 0 }],
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
