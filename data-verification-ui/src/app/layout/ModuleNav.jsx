import { NavLink } from "react-router-dom";

const MODULES = [
  { to: "/news", label: "科技即時報" },
  { to: "/dashboard", label: "數據儀表板" },
  { to: "/insights", label: "投資觀點" },
  { to: "/columns", label: "科技專欄" },
  { to: "/portfolio", label: "Portfolio" },
];

export default function ModuleNav() {
  return (
    <nav
      className="module-nav flex flex-nowrap gap-1 overflow-x-auto border-b border-white/10 bg-black/20 px-2 py-2 md:hidden"
      aria-label="Portal 模組"
    >
      {MODULES.map(({ to, label }) => (
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
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
