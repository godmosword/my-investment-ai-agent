import { tailwindThemeExtend } from "./src/design/tokens.js";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      ...tailwindThemeExtend,
    },
  },
  plugins: [],
};
