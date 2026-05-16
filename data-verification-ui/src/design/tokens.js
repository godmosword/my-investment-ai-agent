/**
 * PWA design tokens for the dark institutional terminal theme.
 * Tailwind imports `theme.extend` from here; React components may import directly.
 * Keep these values aligned with `src/index.css` `:root`.
 */

/** @typedef {'full' | 'lite' | 'crypto-only'} BriefProfileLabel */

export const palette = {
  regime: {
    on: "#34d399",
    neutral: "#fbbf24",
    off: "#f87171",
  },
  accent: "#22d3ee",
  accent2: "#f59e0b",
  danger: "#f87171",
  warn: "#fbbf24",
  ok: "#34d399",
};

/** Tailwind `theme.extend` 片段（與 palette 同步，勿單獨改一邊） */
export const tailwindThemeExtend = {
  colors: {
    regime: palette.regime,
    qs: {
      accent: palette.accent,
      accent2: palette.accent2,
      danger: palette.danger,
      warn: palette.warn,
      ok: palette.ok,
    },
  },
};

export const profileLabels = {
  full: "full",
  lite: "lite",
  "crypto-only": "crypto-only",
};

/** 字級（rem）— 與 `/design`、Report 長文區塊對齊 */
export const typography = {
  /** 頁標題 */
  pageTitle: "1.35rem",
  /** 區塊標題 */
  section: "0.95rem",
  /** 內文／卡片 */
  body: "0.875rem",
  /** KPI 數字 */
  metricValue: "1.1rem",
  /** 輔助說明 */
  caption: "0.7rem",
};

/** 間距（px）— 與現有 card／grid 視覺密度一致 */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

/** 圓角（px） */
export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
};

/** 陰影（任意值字串，供 inline style 或未來 Tailwind plugin） */
export const shadow = {
  card: "0 12px 30px rgba(0, 0, 0, 0.18)",
  inset: "inset 0 1px 0 rgba(255, 255, 255, 0.05)",
};
