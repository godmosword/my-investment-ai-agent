/** 外部／內部來源連結（審計用） */
export default function SourceLink({ href, children, className = "", external = true }) {
  if (!href) return null;
  return external ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className={`qs-source-link text-[12px] text-[var(--accent)] underline-offset-2 hover:underline ${className}`}
    >
      {children ?? href}
    </a>
  ) : (
    <a href={href} className={`qs-source-link text-[12px] text-[var(--accent)] underline-offset-2 hover:underline ${className}`}>
      {children ?? href}
    </a>
  );
}
