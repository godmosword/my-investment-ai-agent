import importPlugin from "eslint-plugin-import";
import globals from "globals";

/** 與 `TERMINAL_FRONTEND_PLAN.md`／隊列 26 模組邊界一致。 */
const MODULES = [
  "daily-brief",
  "news",
  "dashboard",
  "insights",
  "columns",
  "portfolio",
  "investment-analysis",
  "industry-trends",
  "quant-trading",
];

const zones = [];
for (const target of MODULES) {
  for (const from of MODULES) {
    if (target === from) continue;
    zones.push({
      target: `./src/modules/${target}`,
      from: `./src/modules/${from}`,
      message: `模組邊界：禁止從「${from}」import 至「${target}」；共用碼請放 components/hooks/lib。`,
    });
  }
}

export default [
  { ignores: ["dist/**", "dev-dist/**", "e2e/**", "public/**"] },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: { ...globals.browser },
    },
    plugins: { import: importPlugin },
    rules: {
      "import/no-restricted-paths": ["error", { zones }],
    },
  },
];
