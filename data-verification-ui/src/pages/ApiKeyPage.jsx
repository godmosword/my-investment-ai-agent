import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { QSILICON_MASTER_KEY_STORAGE } from "../lib/siliconApiHeaders";

export default function ApiKeyPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [hint, setHint] = useState("");

  const returnPath = useMemo(() => {
    const raw = (params.get("return") || "").trim();
    if (!raw || raw === "/api-key") return "/briefs";
    try {
      const u = new URL(raw, window.location.origin);
      if (u.pathname === "/api-key") return "/briefs";
      return `${u.pathname}${u.search}${u.hash}`;
    } catch {
      return "/briefs";
    }
  }, [params]);

  const onSave = useCallback(() => {
    const k = value.trim();
    if (!k) {
      setHint("請輸入主金鑰");
      return;
    }
    try {
      localStorage.setItem(QSILICON_MASTER_KEY_STORAGE, k);
      setHint("已儲存，正在返回…");
      navigate(returnPath, { replace: true });
    } catch (e) {
      setHint(`無法寫入 localStorage：${e?.message || e}`);
    }
  }, [navigate, returnPath, value]);

  return (
    <div className="api-key-page px-3 py-6 pb-24">
      <h1 className="mb-2 text-lg font-semibold tracking-tight">API 認證</h1>
      <p className="mb-4 text-[13px] leading-snug text-[var(--muted)]">
        後端已啟用 <code className="font-mono">QSILICON_MASTER_KEY</code> 時，瀏覽器請求須帶{" "}
        <code className="font-mono">X-Q-Silicon-Key</code>。此處寫入之值會存於{" "}
        <code className="font-mono">localStorage.{QSILICON_MASTER_KEY_STORAGE}</code>
        ，並優先於建置變數 <code className="font-mono">VITE_QSILICON_KEY</code>。
      </p>
      <div className="card max-w-md p-3">
        <label className="mb-1 block text-[12px] text-[var(--muted)]">主金鑰</label>
        <input
          type="password"
          autoComplete="off"
          className="mb-3 w-full rounded border border-[color:var(--border)] bg-black/25 px-2 py-2 font-mono text-[13px]"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="與伺服端 QSILICON_MASTER_KEY 相同"
        />
        <button
          type="button"
          className="rounded bg-emerald-700 px-3 py-2 text-[13px] font-medium text-white hover:bg-emerald-600"
          onClick={onSave}
        >
          儲存並繼續
        </button>
        {hint ? <p className="mt-2 text-[12px] text-amber-200/90">{hint}</p> : null}
      </div>
    </div>
  );
}
