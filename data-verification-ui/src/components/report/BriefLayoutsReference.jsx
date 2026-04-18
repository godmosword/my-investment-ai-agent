import { useBriefLayouts } from "../../hooks/useApi";

/**
 * V3：`GET /api/brief-layouts` 唯讀清單（營運／開發對照 config/brief_layouts）。
 */
export default function BriefLayoutsReference() {
  const { data, isLoading, error } = useBriefLayouts();
  const layouts = Array.isArray(data?.layouts) ? data.layouts : [];

  return (
    <details className="brief-layouts-ref card mb-3">
      <summary className="brief-layouts-ref__summary cursor-pointer px-3 py-2 text-[13px] font-semibold outline-none">
        版面 YAML 清單（唯讀）
      </summary>
      <div className="border-t border-[color:var(--border)] px-3 pb-3 pt-2 text-[12px]">
        <p className="mb-2 text-[var(--muted)]">
          對應後端 <code className="rounded bg-black/20 px-1 py-0.5 font-mono text-[11px]">config/brief_layouts/*.yaml</code>
          ；合併仍以伺服器 <code className="rounded bg-black/20 px-1 py-0.5 font-mono text-[11px]">BRIEF_LAYOUT_FILE</code> 為準。
        </p>
        {isLoading ? <div className="text-[var(--muted)]">載入中…</div> : null}
        {error ? (
          <div className="text-[#f87171]">無法載入：{error.message}</div>
        ) : null}
        {!isLoading && !error && layouts.length === 0 ? (
          <div className="text-[var(--muted)]">目前無 YAML 檔案。</div>
        ) : null}
        {!isLoading && layouts.length > 0 ? (
          <ul className="m-0 list-none space-y-2 p-0">
            {layouts.map((row) => (
              <li key={row.filename} className="rounded border border-[color:var(--border)] bg-black/10 px-2 py-1.5 font-mono text-[11px]">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-emerald-200/90">{row.filename}</span>
                  {row.path ? (
                    <span className="text-[var(--muted)]" title={row.path}>
                      {row.path}
                    </span>
                  ) : null}
                </div>
                {row.applies_to_profile ? (
                  <div className="mt-1 text-[var(--muted)]">
                    applies_to_profile:{" "}
                    <span className="text-emerald-100/90">{row.applies_to_profile}</span>
                  </div>
                ) : null}
                {Array.isArray(row.blocks) && row.blocks.length > 0 ? (
                  <ol className="mt-1 mb-0 list-decimal pl-5 text-emerald-100/85">
                    {row.blocks.map((b, i) => (
                      <li key={`${row.filename}-${i}-${b}`}>{b}</li>
                    ))}
                  </ol>
                ) : null}
                {row.parse_error ? (
                  <div className="mt-1 text-[#f87171]">解析：{row.parse_error}</div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  );
}
