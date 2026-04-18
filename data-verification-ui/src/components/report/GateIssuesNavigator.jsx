import { blockSectionDomId } from "./blockAnchors";
import { gateIssueLiClass } from "./gateIssueSeverity";

/**
 * 從 ``gate_summary`` 依區塊導航至 ``#block-*``（visualization_plan V4 Gate drawer 的漸進版）。
 * @param {{
 *   issuesByBlock: Record<string, string[]>,
 *   issuesUnmapped: string[],
 *   className?: string,
 * }} props
 */
export default function GateIssuesNavigator({ issuesByBlock, issuesUnmapped, className = "" }) {
  const entries = Object.entries(issuesByBlock || {}).filter(
    ([, lines]) => Array.isArray(lines) && lines.length > 0
  );
  const unmapped = Array.isArray(issuesUnmapped) ? issuesUnmapped.filter(Boolean) : [];
  if (entries.length === 0 && unmapped.length === 0) return null;

  return (
    <details
      className={`card mb-3 border border-[rgba(248,113,113,0.25)] bg-[rgba(248,113,113,0.04)] ${className}`}
    >
      <summary
        className="cursor-pointer list-inside px-3 py-2.5 text-[13px] font-semibold outline-none marker:text-[var(--muted)]"
        style={{ listStylePosition: "outside", paddingLeft: "1.75rem" }}
      >
        依區塊瀏覽 Gate 問題（錨點）
      </summary>
      <div className="border-t border-[color:rgba(248,113,113,0.15)] px-3 pb-3 pt-2 text-[12px]">
        <p className="mb-3 text-[var(--muted)]">
          點區塊代號跳至對應段落；完整 issue 文案見上方橫幅清單。
        </p>
        <ul className="m-0 space-y-4 p-0">
          {entries.map(([bid, lines]) => (
            <li key={bid} className="list-none">
              <a
                href={`#${blockSectionDomId(bid)}`}
                className="inline-flex items-center gap-2 font-mono text-[12px] text-emerald-200/90 underline-offset-2 hover:underline"
              >
                #{bid}
              </a>
              <span className="text-[var(--muted)]"> · {lines.length} 則</span>
              <ul className="mt-1.5 list-disc pl-5 text-[11px] text-[var(--muted)]">
                {lines.slice(0, 4).map((line, i) => (
                  <li key={i} className={gateIssueLiClass(line)}>
                    {line}
                  </li>
                ))}
                {lines.length > 4 ? (
                  <li className="italic">… 另有 {lines.length - 4} 則</li>
                ) : null}
              </ul>
            </li>
          ))}
        </ul>
        {unmapped.length > 0 ? (
          <div className="mt-4 border-t border-[color:var(--border)] pt-3">
            <div className="mb-2 text-[11px] font-semibold text-[var(--muted)]">未能對應區塊</div>
            <ul className="m-0 list-disc space-y-1 pl-5 text-[11px] text-[var(--muted)]">
              {unmapped.slice(0, 8).map((line, i) => (
                <li key={i} className={gateIssueLiClass(line)}>
                  {line}
                </li>
              ))}
            </ul>
            {unmapped.length > 8 ? (
              <div className="mt-2 text-[11px] text-[var(--muted)]">… 共 {unmapped.length} 則</div>
            ) : null}
          </div>
        ) : null}
      </div>
    </details>
  );
}
