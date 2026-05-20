import ModuleNav from "./ModuleNav";
import SideNav from "./SideNav";
import TerminalCommandBar from "../../components/TerminalCommandBar";
import GlobalGateBadge from "../../components/GlobalGateBadge";
import GlobalWatchlistDock from "../../components/GlobalWatchlistDock";
import useKeyboardShortcuts from "../../hooks/useKeyboardShortcuts";

export default function Shell({ children, hideModuleNav = false }) {
  useKeyboardShortcuts();
  return (
    <div className="app-shell flex min-h-0 flex-1 flex-col md:flex-row">
      {!hideModuleNav ? <SideNav /> : null}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <a href="#main-content" className="skip-to-main">
          略過導覽至主內容
        </a>
        {!hideModuleNav ? <ModuleNav /> : null}
        {!hideModuleNav ? (
          <TerminalCommandBar trailing={<GlobalGateBadge />} />
        ) : null}
        {children}
        {!hideModuleNav ? <GlobalWatchlistDock /> : null}
      </div>
    </div>
  );
}
