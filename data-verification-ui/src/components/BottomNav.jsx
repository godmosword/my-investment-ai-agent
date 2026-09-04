import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/news",      icon: "📰", label: "科技即時報", short: "新聞" },
  { to: "/dashboard", icon: "📊", label: "數據儀表板", short: "儀表" },
  { to: "/insights",  icon: "🖥️", label: "投資觀點", short: "觀點" },
  { to: "/columns",   icon: "🏭", label: "科技專欄", short: "專欄" },
  { to: "/portfolio", icon: "📌", label: "投資組合", short: "組合" },
  { to: "/settings", icon: "⚙️", label: "設定", short: "設定" },
];

export default function BottomNav() {
  return (
    <nav data-testid="bottom-nav" className="bottom-nav" aria-label="主導航（底部）">
      {TABS.map(({ to, icon, label, short }) => (
        <NavLink
          key={to}
          to={to}
          end
          data-testid={`bottom-nav-${to.replace(/^\//, "")}`}
          className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
          aria-label={label}
          title={label}
        >
          <span className="nav-icon" aria-hidden="true">{icon}</span>
          <span className="nav-item__label" data-testid={`bottom-nav-${to.replace(/^\//, "")}-short`}>{short}</span>
        </NavLink>
      ))}
    </nav>
  );
}
