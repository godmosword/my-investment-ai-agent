/**
 * PWA 設計 token（Visualization Plan V1）
 * Tailwind：`theme.extend` 由此匯入；React 組件可直接 import。
 * 與 `src/index.css` `:root` 視覺對齊（深色機構風、青綠 accent）。
 */

/** @typedef {'full' | 'lite' | 'crypto-only'} BriefProfileLabel */

export const palette = {
  regime: {
    /** 風險偏好／偏多語境 */
    on: "#34d399",
    neutral: "#fbbf24",
    off: "#f87171",
  },
  accent: "#2ee6be",
  accent2: "#8b5cf6",
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
