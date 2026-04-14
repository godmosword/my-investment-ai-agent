import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const e2eBuild = process.env.VITE_E2E === "1";

export default defineConfig({
  plugins: [
    react(),
    ...(e2eBuild
      ? []
      : [
          VitePWA({
            registerType: "autoUpdate",
            manifest: {
              name: "Q-Silicon War Room",
              short_name: "Q-Silicon",
              description: "Institutional crypto & AI investment daily report",
              theme_color: "#0e1117",
              background_color: "#0e1117",
              display: "standalone",
              orientation: "portrait",
              start_url: "/",
              icons: [
                { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
                { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
              ],
            },
            workbox: {
              globPatterns: ["**/*.{js,css,html,ico,png,svg}"],
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
});
