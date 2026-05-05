import ModuleNav from "./ModuleNav";

export default function Shell({ children, hideModuleNav = false }) {
  return (
    <div className="app-shell flex min-h-0 flex-1 flex-col">
      {!hideModuleNav ? <ModuleNav /> : null}
      {children}
    </div>
  );
}
