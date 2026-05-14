/** Same-tab workspace reload (dock + future split views). Cross-tab uses `storage`. */
export const QSI_WORKSPACE_CHANGED_EVENT = "qsi_workspace_changed";

export function emitWorkspaceChanged() {
  try {
    globalThis.dispatchEvent(new CustomEvent(QSI_WORKSPACE_CHANGED_EVENT));
  } catch {
    /* ignore */
  }
}
