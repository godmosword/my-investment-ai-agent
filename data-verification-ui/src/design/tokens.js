/**
 * PWA 設計 token（Apple × Muji 亮色主題）
 * Tailwind：`theme.extend` 由此匯入；React 組件可直接 import。
 * 與 `src/index.css` `:root` 視覺對齊（暖奶油底、深青綠主色、光底高對比）。
 */

/** @typedef {'full' | 'lite' | 'crypto-only'} BriefProfileLabel */

export const palette = {
  regime: {
    /** 風險偏好／偏多語境 */
    on: "#059669",
    neutral: "#d97706",
    off: "#dc2626",
  },
  accent: "#0a7c68",
  accent2: "#6d28d9",
  danger: "#dc2626",
  warn: "#d97706",
  ok: "#059669",
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
  card: "0 1px 4px rgba(0, 0, 0, 0.06), 0 4px 16px rgba(0, 0, 0, 0.04)",
  inset: "inset 0 1px 0 rgba(255, 255, 255, 0.8)",
};
