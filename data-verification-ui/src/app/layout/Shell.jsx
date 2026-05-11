import ModuleNav from "./ModuleNav";
import SideNav from "./SideNav";
import TerminalCommandBar from "../../components/TerminalCommandBar";
import GlobalGateBadge from "../../components/GlobalGateBadge";

export default function Shell({ children, hideModuleNav = false }) {
  return (
    <div className="app-shell flex min-h-0 flex-1 flex-col md:flex-row">
      {!hideModuleNav ? <SideNav /> : null}
      <div className="flex min-h-0 flex-1 flex-col">
        {!hideModuleNav ? <ModuleNav /> : null}
        {!hideModuleNav ? (
          <TerminalCommandBar trailing={<GlobalGateBadge />} />
        ) : null}
        {children}
      </div>
    </div>
  );
}
