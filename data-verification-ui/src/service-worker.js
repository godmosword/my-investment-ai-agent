/**
 * InjectManifest service worker: precaching + notification deep links (#block-*).
 * @see src/components/report/blockAnchors.js blockSectionDomId
 */
/// <reference lib="webworker" />

import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";
import { registerRoute } from "workbox-routing";
import { NetworkFirst, NetworkOnly } from "workbox-strategies";

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

/**
 * 保守 runtimeCaching：不碰 /api/*（永遠走網路）；HTML 導覽 NetworkFirst 以便離線時能看到上次頁面（若曾快取）。
 * Precache 仍負責 build 靜態資產。
 */
registerRoute(({ url }) => url.pathname.startsWith("/api"), new NetworkOnly());

registerRoute(
  ({ request }) => request.mode === "navigate",
  new NetworkFirst({
    cacheName: "qs-pages-nav",
    networkTimeoutSeconds: 10,
  }),
);

registerRoute(
  ({ url, request }) =>
    url.origin === self.location.origin &&
    request.destination !== "" &&
    ["script", "style", "worker"].includes(request.destination),
  new NetworkFirst({
    cacheName: "qs-runtime-assets",
    networkTimeoutSeconds: 10,
  }),
);

function blockSectionFragment(blockId) {
  const s = String(blockId ?? "");
  return `block-${s.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

function resolveNotificationUrl(data) {
  const d = data && typeof data === "object" ? data : {};
  if (typeof d.url === "string" && (d.url.startsWith("http://") || d.url.startsWith("https://"))) {
    return d.url;
  }
  const dateStr = d.report_date || d.reportDate;
  const blockRaw = d.block_id != null ? d.block_id : d.blockId;
  const base = new URL(self.registration.scope);
  if (!dateStr || typeof dateStr !== "string" || !String(dateStr).trim()) {
    return base.href;
  }
  const path = `report/${encodeURIComponent(String(dateStr).trim())}`;
  let hash = "";
  if (blockRaw != null && String(blockRaw).trim()) {
    hash = `#${blockSectionFragment(String(blockRaw).trim())}`;
  }
  return new URL(path + hash, base).href;
}

async function openOrFocus(url) {
  const clientsArr = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const origin = new URL(self.registration.scope).origin;
  for (const c of clientsArr) {
    if (typeof c.url === "string" && c.url.startsWith(origin) && "focus" in c) {
      if ("navigate" in c && typeof c.navigate === "function") {
        await c.navigate(url);
        return c.focus();
      }
    }
  }
  if (self.clients.openWindow) {
    return self.clients.openWindow(url);
  }
  return undefined;
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = resolveNotificationUrl(event.notification.data);
  event.waitUntil(openOrFocus(url));
});
