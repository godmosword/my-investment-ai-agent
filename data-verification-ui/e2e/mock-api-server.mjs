/**
 * Minimal mock API for Playwright (Bloomberg §6 cross-route price alignment).
 * Serves GET /api/symbols/BTC/snapshot and /api/symbols/BTC/quote with matching OHLC tail vs quote.last.
 */
import http from "node:http";

const PORT = Number(process.env.E2E_MOCK_API_PORT || "9999");
const LAST = 50000.125;

const snapshotBody = {
  symbol: "BTC",
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
    { time: "2026-04-12", open: 1, high: 2, low: 0.5, close: 49000 },
    { time: "2026-04-13", open: 1, high: 2, low: 0.5, close: 49500 },
    { time: "2026-04-14", open: 1, high: 2, low: 0.5, close: LAST },
  ],
  event_markers: [],
  recommendations: [],
  report_links: [],
  data_provenance: {
    ohlc: { source: "yfinance", as_of: "2026-04-14", interval: "1d", underlying_symbol: "BTC-USD" },
    daily_metrics: { source: "bigquery", table_id: "e2e.mock", as_of: "2026-04-14T00:00:00+00:00" },
    recommendations: { source: "bigquery", table_id: "e2e.mock", query_window_days: 30, as_of: "2026-04-14T00:00:00+00:00" },
    price_alignment: {
      note: "e2e mock",
      ohlc_vs_quote: {
        ohlc_last_close: LAST,
        quote_last: LAST,
        abs_diff: 0,
        rel_diff: 0,
        aligned: true,
        quote_error: null,
      },
    },
  },
  price_alignment: {
    ohlc_last_close: LAST,
    quote_last: LAST,
    abs_diff: 0,
    rel_diff: 0,
    aligned: true,
    quote_error: null,
  },
};

const quoteBody = {
  symbol: "BTC",
  as_of: "2026-04-14T00:00:00Z",
  source: "yfinance",
  underlying_symbol: "BTC-USD",
  last: LAST,
  currency: "USD",
  change_pct_1d: 0.01,
  cached: false,
  data_provenance: {
    price: {
      source: "yfinance",
      as_of: "2026-04-14T00:00:00Z",
      interval: "1d",
      underlying_symbol: "BTC-USD",
    },
  },
};

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
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "*",
    });
    res.end();
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
  if (url.pathname === "/api/symbols/BTC/snapshot") {
    sendJson(res, 200, snapshotBody);
    return;
  }
  if (url.pathname === "/api/symbols/BTC/quote") {
    sendJson(res, 200, quoteBody);
    return;
  }
  if (url.pathname === "/api/war-room/latest") {
    sendJson(res, 200, { gate_failure: null, scratchpad: null, execution_intents: [] });
    return;
  }
  if (url.pathname.startsWith("/api/execution-intents/allowed-statuses")) {
    sendJson(res, 200, { statuses: ["PENDING_REVIEW"], client_patchable: [] });
    return;
  }
  if (url.pathname.startsWith("/api/execution-intents")) {
    sendJson(res, 200, []);
    return;
  }
  if (url.pathname === "/api/reports/" + url.pathname.slice("/api/reports/".length)) {
    sendJson(res, 200, { report_date: "2026-04-14", recommendations: [] });
    return;
  }
  const reportsListMatch = url.pathname.match(/^\/api\/reports\/?$/);
  if (reportsListMatch) {
    sendJson(res, 200, []);
    return;
  }
  const reportDayMatch = url.pathname.match(/^\/api\/reports\/(\d{4}-\d{2}-\d{2})$/);
  if (reportDayMatch) {
    sendJson(res, 200, {
      report_date: reportDayMatch[1],
      timestamp: "2026-04-14T00:00:00Z",
      recommendations: [],
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
