/** V2 native mapping from DailyBriefReport JSON → block render models (fallback to legacy elsewhere). */

import { legacyContentForBlock } from "./legacyBlockContent";

function joinLines(arr, sep = "\n") {
  if (!Array.isArray(arr)) return "";
  return arr.map((x) => String(x ?? "").trim()).filter(Boolean).join(sep);
}

function regimeLabel(regime) {
  const r = String(regime ?? "").toLowerCase();
  if (r === "risk_on") return "風險偏好（risk_on）";
  if (r === "risk_off") return "避險（risk_off）";
  if (r === "neutral") return "中性（neutral）";
  return regime ? String(regime) : "";
}

/** Parse first numeric token from dashboard / leg strings (e.g. "95,000 (+2%)"). */
export function parseLeadingNumber(raw) {
  if (raw == null || raw === "") return null;
  const m = String(raw).match(/-?\d[\d,.]*/);
  if (!m) return null;
  const n = Number(m[0].replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

/** QSREC TradeRecommendation (entry/target/stop) → TradeCard shape (entry_price / …). */
export function normalizeTradeRecommendation(t) {
  if (!t || typeof t !== "object") return t;
  const out = { ...t };
  if (out.entry_price == null && out.entry != null) out.entry_price = out.entry;
  if (out.target_price == null && out.target != null) out.target_price = out.target;
  if (out.stop_price == null && out.stop != null) out.stop_price = out.stop;
  return out;
}

/** ExecutableTradeLeg → TradeCard-compatible object (prices best-effort parsed). */
export function executableLegToTradeShape(leg) {
  if (!leg || typeof leg !== "object") return {};
  return {
    asset: leg.asset,
    direction: leg.direction,
    confidence: leg.star_rating,
    current_price: parseLeadingNumber(leg.current_price),
    entry_price: parseLeadingNumber(leg.entry),
    target_price: parseLeadingNumber(leg.target),
    stop_price: parseLeadingNumber(leg.stop),
    trigger: leg.trigger,
    invalidation: leg.invalidation,
    narrative: leg.narrative,
    position_pct: parseLeadingNumber(leg.position_pct),
    rr_ratio: leg.rr,
    timeframe: "",
    bull_scenario: leg.bull_scenario,
    base_scenario: leg.base_scenario,
    bear_scenario: leg.bear_scenario,
  };
}

function wrapTradesPayload(rows, opts = {}) {
  const { introHtml, disclaimer } = opts;
  if (!introHtml && !disclaimer) return rows;
  return { rows: Array.isArray(rows) ? rows : [], introHtml, disclaimer };
}

export function unwrapTradesPayload(payload) {
  if (Array.isArray(payload)) return { rows: payload, introHtml: undefined, disclaimer: undefined };
  return {
    rows: Array.isArray(payload?.rows) ? payload.rows : [],
    introHtml: payload?.introHtml,
    disclaimer: payload?.disclaimer,
  };
}

/**
 * Map one logical block to structured content. Returns { kind: "skip" } if this block
 * has nothing to show from DailyBriefReport (caller may fall back to legacy).
 *
 * Kinds: skip | text | news | trades | news_items | metrics | html | roundtable
 */
export function structuredContentForBlock(blockId, dbr) {
  if (!dbr || typeof dbr !== "object") return { kind: "skip" };

  const crypto = dbr.crypto || {};
  const ai = dbr.ai || {};

  switch (blockId) {
    case "header": {
      const date = crypto.report_title_date;
      if (!date) return { kind: "skip" };
      return { kind: "text", payload: `Q-Silicon 日報 · ${date}` };
    }
    case "exec_summary": {
      const bullets = Array.isArray(crypto.exec_summary) ? crypto.exec_summary.filter(Boolean) : [];
      const one = String(crypto.investment_thesis_one_liner || "").trim();
      const parts = [];
      if (one) parts.push(`【投資命題】${one}`);
      if (bullets.length) parts.push(bullets.map((b) => `• ${b}`).join("\n"));
      const payload = parts.join("\n\n").trim();
      return payload ? { kind: "text", payload } : { kind: "skip" };
    }
    case "previous_recs": {
      const html = String(dbr.previous_recs_html || "").trim();
      return html ? { kind: "html", payload: html } : { kind: "skip" };
    }
    case "market_mode": {
      const m = crypto.market || {};
      const regime = regimeLabel(m.regime);
      const sfx = String(m.score_suffix || "").trim();
      const scoreLines = joinLines(m.scorecard_lines);
      const nod = String(crypto.narrative_of_day || "").trim();
      const bits = [
        nod && `【今日主敘事】${nod}`,
        regime && `【制度】${regime}${sfx ? ` ${sfx}` : ""}`,
        scoreLines && `【評分卡】\n${scoreLines}`,
      ].filter(Boolean);
      const payload = bits.join("\n\n");
      return payload ? { kind: "text", payload } : { kind: "skip" };
    }
    case "macro_framework": {
      const lines = joinLines(crypto.macro_framework_lines);
      return lines ? { kind: "text", payload: lines } : { kind: "skip" };
    }
    case "prediction_markets": {
      const lines = joinLines(crypto.prediction_market_highlight_lines);
      return lines ? { kind: "text", payload: lines } : { kind: "skip" };
    }
    case "crypto_dashboard": {
      const dash = Array.isArray(crypto.dashboard) ? crypto.dashboard : [];
      return dash.length ? { kind: "metrics", payload: dash } : { kind: "skip" };
    }
    case "crypto_news": {
      const items = Array.isArray(crypto.news) ? crypto.news : [];
      return items.length ? { kind: "news_items", payload: items } : { kind: "skip" };
    }
    case "crypto_chatter": {
      const chatter = Array.isArray(crypto.chatter) ? crypto.chatter : [];
      const xh = Array.isArray(crypto.x_highlights) ? crypto.x_highlights.filter(Boolean) : [];
      const parts = [];
      if (chatter.length) {
        parts.push(chatter.map((c) => String(c?.text || "").trim()).filter(Boolean).join("\n"));
      }
      if (xh.length) {
        parts.push(`【X 精選】\n${xh.join("\n")}`);
      }
      const payload = parts.filter(Boolean).join("\n\n").trim();
      return payload ? { kind: "text", payload } : { kind: "skip" };
    }
    case "crypto_trades": {
      const legs = Array.isArray(crypto.trade_legs) ? crypto.trade_legs : [];
      const mapped = legs.map(executableLegToTradeShape);
      const intro = String(crypto.crypto_block4_recommendation_line || "").trim();
      if (!mapped.length && !intro) return { kind: "skip" };
      return {
        kind: "trades",
        payload: wrapTradesPayload(mapped, { introHtml: intro || undefined }),
      };
    }
    case "ai_bridge": {
      const lines = joinLines(ai.macro_bridge_lines);
      return lines ? { kind: "text", payload: lines } : { kind: "skip" };
    }
    case "ai_dashboard": {
      const dash = Array.isArray(ai.dashboard) ? ai.dashboard : [];
      return dash.length ? { kind: "metrics", payload: dash } : { kind: "skip" };
    }
    case "ai_news": {
      const items = Array.isArray(ai.news) ? ai.news : [];
      return items.length ? { kind: "news_items", payload: items } : { kind: "skip" };
    }
    case "ai_chatter": {
      const chatter = Array.isArray(ai.chatter) ? ai.chatter : [];
      const xh = Array.isArray(ai.x_highlights) ? ai.x_highlights.filter(Boolean) : [];
      const parts = [];
      if (chatter.length) {
        parts.push(chatter.map((c) => String(c?.text || "").trim()).filter(Boolean).join("\n"));
      }
      if (xh.length) parts.push(`【X 精選】\n${xh.join("\n")}`);
      const payload = parts.filter(Boolean).join("\n\n").trim();
      return payload ? { kind: "text", payload } : { kind: "skip" };
    }
    case "ai_trades": {
      const legs = Array.isArray(ai.trade_legs) ? ai.trade_legs : [];
      const mapped = legs.map(executableLegToTradeShape);
      const intro = String(ai.ai_block4_recommendation_line || "").trim();
      if (!mapped.length && !intro) return { kind: "skip" };
      return {
        kind: "trades",
        payload: wrapTradesPayload(mapped, { introHtml: intro || undefined }),
      };
    }
    case "current_affairs_roundtable": {
      const rt = dbr.current_affairs_roundtable;
      if (!rt || typeof rt !== "object") return { kind: "skip" };
      const topic = String(rt.topic || "").trim();
      const voices = Array.isArray(rt.voices) ? rt.voices : [];
      if (!topic && !voices.length) return { kind: "skip" };
      return { kind: "roundtable", payload: rt };
    }
    case "institutional_view": {
      const parts = [];
      const push = (label, body) => {
        const b = String(body || "").trim();
        if (b) parts.push(`${label}\n${b}`);
      };
      push("【投資命題】", crypto.investment_thesis_one_liner);
      const list = (arr, label) => {
        const j = joinLines(arr);
        if (j) parts.push(`${label}\n${j}`);
      };
      list(crypto.thesis_supporting_points, "【支持論點】");
      list(crypto.thesis_contrary_points, "【反駁／風險】");
      list(crypto.key_assumptions_lines, "【關鍵假設】");
      push("【敘事失效】", crypto.narrative_invalidation_summary);
      push("【組合與曝險框架】", crypto.portfolio_framing_summary);
      push("【三情境機率】", crypto.scenario_probability_notes);
      list(crypto.event_calendar_lines, "【近端事件】");
      push("【加密週期與估值錨】", crypto.crypto_cycle_valuation_notes);
      push("【美股估值框架】", crypto.equity_valuation_framing);
      const thesisText = parts.filter(Boolean).join("\n\n");
      const disc = String(dbr.institutional_disclaimer_html || "").trim();
      if (!thesisText && !disc) return { kind: "skip" };
      if (disc && !thesisText) return { kind: "html", payload: disc };
      if (thesisText && !disc) return { kind: "text", payload: thesisText };
      return { kind: "institutional_split", payload: { thesisText, disclaimerHtml: disc } };
    }
    case "source_health": {
      const raw = String(dbr.source_observability_block || "").trim();
      if (!raw) return { kind: "skip" };
      if (raw.includes("<")) return { kind: "html", payload: raw };
      return { kind: "text", payload: raw };
    }
    case "qsrec": {
      const c = Array.isArray(crypto.qsrec) ? crypto.qsrec : [];
      const a = Array.isArray(ai.qsrec) ? ai.qsrec : [];
      const merged = [...c, ...a].map(normalizeTradeRecommendation);
      const disc = String(dbr.low_confidence_disclaimer || "").trim();
      if (!merged.length && !disc) return { kind: "skip" };
      return {
        kind: "trades",
        payload: wrapTradesPayload(merged, { disclaimer: disc || undefined }),
      };
    }
    default:
      return { kind: "skip" };
  }
}

/**
 * Prefer DailyBriefReport-native content when `structuredOk` and model present; else legacy BQ summary.
 */
export function blockContentForBlock(blockId, { dbr, legacy, structuredOk }) {
  if (structuredOk && dbr && typeof dbr === "object") {
    const s = structuredContentForBlock(blockId, dbr);
    if (s.kind !== "skip") return s;
  }
  return legacyContentForBlock(blockId, legacy);
}
