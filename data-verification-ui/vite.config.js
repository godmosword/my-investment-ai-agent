import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const e2eBuild = process.env.VITE_E2E === "1";

/** 將 React／Router 與應用程式碼分離，略縮主 entry（對齊 Master Plan §3.6）。 */
function manualChunks(id) {
  if (!id.includes("node_modules")) return undefined;
  if (id.includes("react-dom")) return "react-dom";
  if (id.includes("react-router")) return "react-router";
  if (id.includes("/react/") || id.includes("\\react\\")) return "react";
  return undefined;
}

export default defineConfig({
  plugins: [
    react(),
    ...(e2eBuild
      ? []
      : [
          VitePWA({
            registerType: "autoUpdate",
            injectRegister: false,
            strategies: "injectManifest",
            srcDir: "src",
            filename: "service-worker.js",
            injectManifest: {
              globPatterns: ["**/*.{js,css,html,ico,png,svg}"],
            },
            manifest: {
              name: "Q-Silicon War Room",
              short_name: "Q-Silicon",
              description: "Institutional crypto & AI investment daily report",
              theme_color: "#0e1117",
              background_color: "#0e1117",
              display: "standalone",
              orientation: "portrait",
              start_url: "/insights",
              icons: [
                { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
                { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
              ],
            },
          }),
        ]),
  ],
  server: {
    proxy: {
      // Proxy /api requests to FastAPI during local dev
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks,
      },
    },
  },
});
