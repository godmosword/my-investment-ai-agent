/**
 * 示範／降級資料提示 — 樣式對齊 `glassbox-demo-banner`（index.css）
 */
export default function MockBanner({ variant = "default", children, className = "" }) {
  const mod = variant === "today" ? "glassbox-demo-banner--today" : "";
  return (
    <div className={`glassbox-demo-banner ${mod} ${className}`} role="status">
      {children}
    </div>
  );
}
