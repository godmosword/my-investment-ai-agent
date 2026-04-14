/**
 * Optional Web Push subscription registration (staging / local experiments).
 *
 * Enable with VITE_WEB_PUSH_REGISTER=1 and a reachable VITE_API_URL where
 * WEB_PUSH_ENABLED=1 on the FastAPI server.
 */
const truthy = (v) => String(v || "").toLowerCase() === "1" || String(v || "").toLowerCase() === "true";

async function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export async function tryRegisterWebPush() {
  if (!truthy(import.meta.env.VITE_WEB_PUSH_REGISTER)) return;
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

  const vapid = (import.meta.env.VITE_WEB_PUSH_VAPID_PUBLIC_KEY || "").trim();
  if (!vapid) {
    console.info("[push] VITE_WEB_PUSH_REGISTER=1 but VITE_WEB_PUSH_VAPID_PUBLIC_KEY missing — skip subscribe");
    return;
  }

  try {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) {
      console.info("[push] no active service worker — skip (build PWA or wait for SW)");
      return;
    }
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapid),
    });
    const j = sub.toJSON();
    const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
    if (!base) {
      console.warn("[push] VITE_API_URL unset — skip POST /api/push/subscribe");
      return;
    }
    const r = await fetch(`${base}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys }),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      console.warn("[push] subscribe HTTP", r.status, t.slice(0, 200));
    }
  } catch (e) {
    console.warn("[push] registration skipped:", e?.message || e);
  }
}
