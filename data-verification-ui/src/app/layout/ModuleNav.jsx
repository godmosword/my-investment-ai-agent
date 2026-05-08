import { NavLink } from "react-router-dom";

const MODULES = [
  { to: "/briefs", label: "日報", short: "日報" },
  { to: "/analysis", label: "投資分析", short: "分析" },
  { to: "/positions", label: "倉位", short: "倉位" },
  { to: "/industries", label: "產業", short: "產業" },
  { to: "/quant", label: "量化", short: "量化" },
];

export default function ModuleNav() {
  return (
    <nav
      className="module-nav flex flex-wrap gap-1 border-b border-white/10 bg-black/20 px-2 py-2 md:hidden"
      aria-label="Portal 模組"
    >
      {MODULES.map(({ to, label, short }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `rounded-md px-2 py-1 text-[12px] no-underline sm:px-3 sm:text-[13px] ${
              isActive ? "bg-emerald-600/40 text-white" : "text-[var(--muted)] hover:bg-white/5"
            }`
          }
          title={label}
        >
          <span className="sm:hidden">{short}</span>
          <span className="hidden sm:inline">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
