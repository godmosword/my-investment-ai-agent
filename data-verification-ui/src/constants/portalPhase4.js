/**
 * Portal Phase 4 — Gate 0 預設（讀者層 × 工作台層 IA）。
 * 維護者若 REVIEW 後要改決策，請同步 `TODOS.md` 隊列 44「Gate 0」段落。
 */
export const PORTAL_PHASE4_GATE0 = {
  /** 工作台「主戰場」兩條路由（對齊 Master Plan 建議預設）。 */
  workbenchPrimaryRoutes: ["/insights", "/portfolio"],
  /** 第三條狀態台（macro）；與上兩條並列於工作台層，但不佔「兩條主戰場」名額。 */
  workbenchMacroRoute: "/dashboard",
  /**
   * 讀者層首屏：避免多區高密度「報價表／矩陣表」。
   * 現有 digest 卡片流（非 HTML table 報價牆）視為符合本旗標。
   */
  readerFirstScreenAvoidDenseTables: true,
  /**
   * 融合第一刀：雙向（讀者層 ↔ 工作台層）。
   * 44c 已在工作台層補回向 CTA、讀者層可帶 `?focus=SYM` 高亮相關卡片。
   */
  fusionDirection: "bidirectional",
  /** 「終端感」保留元素上限（三至五項；供文件／UI 文案對齊）。 */
  terminalToneKeep: ["Command Bar", "mono symbol chips", "macro spark grid", "SSE WATCH", "Workspace dock"],
  /** 工作台關鍵路徑：警報 → 標的／狀態 →（可選）脈絡 — 最大點擊數 N。 */
  maxWorkbenchPathClicks: 3,
};

/** `/insights` 或帶 `?symbol=` 的深連結（重用既有 SymbolDeepDive 契約）。 */
export function insightsSymbolHref(symbol) {
  const s = String(symbol ?? "").trim().toUpperCase();
  if (!s) return "/insights";
  return `/insights?symbol=${encodeURIComponent(s)}`;
}

/** `/news` 或帶 `?focus=SYM` 的回向深連結（44c 融合層使用）。 */
export function newsContextHref(symbol) {
  const s = String(symbol ?? "").trim().toUpperCase();
  if (!s) return "/news";
  return `/news?focus=${encodeURIComponent(s)}`;
}

/** `/columns` 或帶 `?focus=SYM` 的回向深連結（44c 融合層使用）。 */
export function columnsContextHref(symbol) {
  const s = String(symbol ?? "").trim().toUpperCase();
  if (!s) return "/columns";
  return `/columns?focus=${encodeURIComponent(s)}`;
}

/** 文案表（44c）：跨板塊人話 CTA 統一文字，避免 UI 文案散落。 */
export const PORTAL_PHASE4_CTA = {
  toInsights: "去觀點工作台",
  toColumns: "看深度專欄",
  toNews: "看科技即時報",
  workbenchToNews: "回到新聞脈動",
  workbenchToColumns: "看相關專欄",
  symbolToNews: "在新聞中查 {symbol}",
  symbolToColumns: "看 {symbol} 的專欄",
};

/** 套入 symbol 的 CTA 文案 helper。 */
export function ctaWithSymbol(template, symbol) {
  const s = String(symbol ?? "").trim().toUpperCase();
  return String(template || "").replace("{symbol}", s || "標的");
}

/**
 * Command Bar placeholder：讀者頁偏「搜尋／跳轉」語意，工作台頁保留 GO／RUN 語感。
 * @param {string} pathname
 */
export function getTerminalCommandBarPlaceholder(pathname) {
  const raw = String(pathname || "/").trim() || "/";
  const path = raw.split("?")[0] || "/";
  if (path === "/news" || path === "/columns") {
    return "搜尋主題焦點… 或 /insights、/portfolio、AAPL GO、RUN";
  }
  return "AAPL <GO> | /columns | MACRO | RUN";
}

/** Command Bar inline examples：讓 ADR N/R/W/S 邊界在 UI 可見，不新增任何新指令。 */
export function getTerminalCommandExamples(pathname) {
  const raw = String(pathname || "/").trim() || "/";
  const path = raw.split("?")[0] || "/";
  const readerMode = path === "/news" || path === "/columns";
  if (readerMode) {
    return [
      { label: "跳觀點", command: "/insights", note: "純前端導覽" },
      { label: "查標的", command: "AAPL GO", note: "帶到工作台焦點" },
      { label: "啟動研究", command: "RUN", note: "需後端金鑰與節流" },
    ];
  }
  return [
    { label: "切版面", command: "MACRO", note: "前往數據儀表板" },
    { label: "追蹤", command: "AAPL GO → WATCH", note: "寫入本機 watch list" },
    { label: "重跑 Crew", command: "RUN", note: "需後端金鑰與節流" },
  ];
}
