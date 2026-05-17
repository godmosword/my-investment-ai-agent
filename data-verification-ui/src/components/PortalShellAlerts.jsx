import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { QSILICON_API_SHELL_ERROR } from "../lib/siliconApiClient";

const E2E = import.meta.env.VITE_E2E === "1";
const PROD = import.meta.env.PROD;
const NO_API_URL = !String(import.meta.env.VITE_API_URL || "").trim();

/**
 * 全域：production 缺 API 基底、API 網路／5xx 簡訊、SW 待套用更新（401 仍走 useApi）。
 */
export default function PortalShellAlerts() {
  const [apiShellErr, setApiShellErr] = useState(null);
  const [swUpdateReady, setSwUpdateReady] = useState(false);
  const regRef = useRef(null);
  const reloadAfterSkipRef = useRef(false);

  const showMissingApiBanner = PROD && !E2E && NO_API_URL;

  useEffect(() => {
    const onErr = (e) => {
      const d = e?.detail;
      if (!d || typeof d !== "object") return;
      const msg =
        typeof d.message === "string" && d.message.trim()
          ? d.message.trim()
          : d.kind === "network"
            ? "網路連線失敗"
            : "伺服器錯誤";
      setApiShellErr(msg);
    };
    globalThis.addEventListener(QSILICON_API_SHELL_ERROR, onErr);
    return () => globalThis.removeEventListener(QSILICON_API_SHELL_ERROR, onErr);
  }, []);

  useEffect(() => {
    if (!apiShellErr) return undefined;
    const t = globalThis.setTimeout(() => setApiShellErr(null), 12000);
    return () => globalThis.clearTimeout(t);
  }, [apiShellErr]);

  useEffect(() => {
    if (!PROD || E2E || !("serviceWorker" in navigator)) return undefined;

    const onControllerChange = () => {
      if (reloadAfterSkipRef.current) {
        reloadAfterSkipRef.current = false;
        globalThis.location?.reload();
      }
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    let cancelled = false;
    let reg;
    const onUpdateFound = () => {
      const nw = reg?.installing;
      if (!nw) return;
      nw.addEventListener("statechange", () => {
        if (cancelled) return;
        if (nw.state === "installed" && navigator.serviceWorker.controller) {
          setSwUpdateReady(true);
        }
      });
    };

    navigator.serviceWorker
      .register("/service-worker.js")
      .then((r) => {
        if (cancelled) return;
        reg = r;
        regRef.current = r;
        r.addEventListener("updatefound", onUpdateFound);
        if (r.waiting && navigator.serviceWorker.controller) setSwUpdateReady(true);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      if (reg) reg.removeEventListener("updatefound", onUpdateFound);
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
    };
  }, []);

  const applySwUpdate = () => {
    const r = regRef.current;
    if (!r?.waiting) {
      setSwUpdateReady(false);
      return;
    }
    reloadAfterSkipRef.current = true;
    r.waiting.postMessage({ type: "SKIP_WAITING" });
  };

  if (!showMissingApiBanner && !apiShellErr && !swUpdateReady) return null;

  return (
    <div
      className="portal-shell-alerts sticky top-0 z-[200] flex flex-col gap-0 border-b border-amber-700/40 bg-[#1a1510] text-[13px] text-amber-100/95"
      role="region"
      aria-label="系統提示"
    >
      {showMissingApiBanner ? (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <span>
            正式環境未設定 <code className="rounded bg-black/35 px-1 font-mono text-[11px]">VITE_API_URL</code>
            ，API 請求將走同源相對路徑；請於建置時注入或至{" "}
            <Link className="underline decoration-amber-400/80 underline-offset-2" to="/settings">
              設定
            </Link>{" "}
            核對。
          </span>
        </div>
      ) : null}
      {apiShellErr ? (
        <div className="border-t border-amber-800/50 px-3 py-2 text-rose-200/95">
          <span className="font-medium">API：</span>
          {apiShellErr}
        </div>
      ) : null}
      {swUpdateReady ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-amber-800/50 px-3 py-2">
          <span>新版本已就緒，重新整理後套用 Service Worker 更新。</span>
          <button
            type="button"
            className="rounded border border-amber-500/50 bg-amber-800/40 px-2.5 py-1 text-[12px] font-medium text-amber-50 hover:bg-amber-700/50"
            onClick={applySwUpdate}
          >
            套用更新
          </button>
        </div>
      ) : null}
    </div>
  );
}
