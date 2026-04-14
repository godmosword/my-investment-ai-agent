/**
 * Minimal mock API for Playwright (Bloomberg §6 cross-route price alignment).
 * BTC：aligned；SPY：刻意 misaligned（price_alignment.aligned=false）供 Terminal 警告 E2E。
 */
import http from "node:http";

const PORT = Number(process.env.E2E_MOCK_API_PORT || "9999");
const BTC_LAST = 50000.125;
const SPY_OHLC_LAST = 600;
const SPY_QUOTE_LAST = 610.25;
const SPY_REL_DIFF = Math.abs(SPY_QUOTE_LAST - SPY_OHLC_LAST) / SPY_OHLC_LAST;

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
    price_alignment: priceAlignment,
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

const spyMisaligned = {
  ohlc_last_close: SPY_OHLC_LAST,
  quote_last: SPY_QUOTE_LAST,
  abs_diff: SPY_QUOTE_LAST - SPY_OHLC_LAST,
  rel_diff: SPY_REL_DIFF,
  aligned: false,
  quote_error: null,
};

const snapshotBtc = baseSnapshot("BTC", BTC_LAST, btcAligned);
const snapshotSpy = baseSnapshot("SPY", SPY_OHLC_LAST, spyMisaligned);

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
  const snapMatch = url.pathname.match(/^\/api\/symbols\/([^/]+)\/snapshot$/);
  if (snapMatch) {
    const sym = snapMatch[1].toUpperCase();
    if (sym === "BTC") {
      sendJson(res, 200, snapshotBtc);
      return;
    }
    if (sym === "SPY") {
      sendJson(res, 200, snapshotSpy);
      return;
    }
    sendJson(res, 404, { error: "unknown_symbol" });
    return;
  }
  const quoteMatch = url.pathname.match(/^\/api\/symbols\/([^/]+)\/quote$/);
  if (quoteMatch) {
    const sym = quoteMatch[1].toUpperCase();
    if (sym === "BTC") {
      sendJson(res, 200, quoteBody("BTC", BTC_LAST));
      return;
    }
    if (sym === "SPY") {
      sendJson(res, 200, quoteBody("SPY", SPY_QUOTE_LAST));
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
