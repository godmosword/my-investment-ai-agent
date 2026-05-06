/** Map legacy GET /api/reports fields into coarse block placeholders (V2 fallback). */

function normalizeCategory(cat) {
  return String(cat ?? "")
    .trim()
    .toUpperCase();
}

function isCryptoRec(r) {
  const c = normalizeCategory(r.category);
  if (c.includes("CRYPTO") || c === "C") return true;
  const a = String(r.asset ?? "").toUpperCase();
  return ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"].some((x) => a.includes(x));
}

function isAiRec(r) {
  const c = normalizeCategory(r.category);
  if (c.includes("AI") || c.includes("TECH")) return true;
  return !isCryptoRec(r);
}

/**
 * @param {string} blockId
 * @param {Record<string, unknown>} legacy
 * @returns {{ kind: "text" | "news" | "trades" | "exec_summary" | "market_mode" | "skip"; payload?: unknown }}
 */
export function legacyContentForBlock(blockId, legacy) {
  if (!legacy) return { kind: "skip" };

  const recs = Array.isArray(legacy.recommendations) ? legacy.recommendations : [];

  switch (blockId) {
    case "header":
      return { kind: "skip" };
    case "exec_summary": {
      const parts = [legacy.grok_summary, legacy.gpt_summary].filter(Boolean);
      const fallbackText = parts.join("\n\n—\n\n").trim();
      return fallbackText ? { kind: "exec_summary", payload: { fallbackText } } : { kind: "skip" };
    }
    case "market_mode": {
      const bits = [];
      if (legacy.regime_score != null) bits.push(`制度／波動：${legacy.regime_score}`);
      if (legacy.sentiment_score != null) bits.push(`情緒：${Number(legacy.sentiment_score).toFixed(2)}`);
      if (legacy.sopr != null) bits.push(`SOPR：${legacy.sopr}`);
      if (legacy.exchange_netflow != null) bits.push(`交易所淨流：${legacy.exchange_netflow}`);
      const fallbackText = bits.join(" · ").trim();
      return fallbackText ? { kind: "market_mode", payload: { fallbackText } } : { kind: "skip" };
    }
    case "macro_framework":
    case "prediction_markets":
    case "institutional_view":
    case "current_affairs_roundtable":
      return legacy.news_titles
        ? { kind: "news", payload: legacy.news_titles }
        : { kind: "skip" };
    case "previous_recs":
      return recs.length ? { kind: "trades", payload: recs } : { kind: "skip" };
    case "crypto_dashboard":
    case "crypto_news":
    case "crypto_chatter":
      return legacy.grok_summary
        ? { kind: "text", payload: legacy.grok_summary }
        : { kind: "skip" };
    case "ai_bridge":
    case "ai_dashboard":
    case "ai_news":
    case "ai_chatter":
      return legacy.gpt_summary
        ? { kind: "text", payload: legacy.gpt_summary }
        : { kind: "skip" };
    case "crypto_trades": {
      const rows = recs.filter(isCryptoRec);
      return rows.length ? { kind: "trades", payload: rows } : { kind: "skip" };
    }
    case "ai_trades": {
      const rows = recs.filter(isAiRec);
      return rows.length ? { kind: "trades", payload: rows } : { kind: "skip" };
    }
    case "qsrec":
      return recs.length ? { kind: "trades", payload: recs } : { kind: "skip" };
    case "source_health":
      return { kind: "text", payload: "（來源健康度將於結構化報告可用時顯示。）" };
    default:
      return { kind: "skip" };
  }
}

/** Short zh label for block section header */
export function blockSectionTitle(blockId, registryEntry) {
  const macro = registryEntry?.macro_name ?? blockId;
  const map = {
    header: "抬頭",
    exec_summary: "執行摘要",
    previous_recs: "前次建議回顧",
    market_mode: "市場模式",
    macro_framework: "總經框架",
    prediction_markets: "預測市場",
    crypto_dashboard: "幣圈儀表",
    crypto_news: "幣圈新聞",
    crypto_chatter: "幣圈社群",
    crypto_trades: "幣圈交易",
    ai_bridge: "AI 橋接",
    ai_dashboard: "AI 儀表",
    ai_news: "AI 新聞",
    ai_chatter: "AI 社群",
    ai_trades: "AI 交易",
    deep_filing_block: "深度財報核讀",
    agency_finance_block: "Agency 財務研究",
    current_affairs_roundtable: "時事圓桌",
    institutional_view: "機構觀點",
    source_health: "來源健康",
    qsrec: "投資建議",
  };
  return map[blockId] ?? macro.replace(/^telegram_/, "");
}
