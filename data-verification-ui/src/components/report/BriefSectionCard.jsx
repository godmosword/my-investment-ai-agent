import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "qs_brief_card_collapse_v1";

function readCollapsedMap() {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeCollapsedMap(map) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore storage failures
  }
}

/**
 * FE-2 — wrap report block content with a collapsible chevron header.
 * The wrapped child renders its own card/title; this component just adds a
 * compact toggle and hides the body when collapsed. Collapse state persists
 * per ``blockId`` in localStorage.
 */
export default function BriefSectionCard({ blockId, label, children, defaultCollapsed = false }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  useEffect(() => {
    if (!blockId) return;
    const map = readCollapsedMap();
    if (Object.prototype.hasOwnProperty.call(map, blockId)) {
      setCollapsed(Boolean(map[blockId]));
    }
  }, [blockId]);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      if (blockId) {
        const map = readCollapsedMap();
        map[blockId] = next;
        writeCollapsedMap(map);
      }
      return next;
    });
  }, [blockId]);

  const buttonLabel = collapsed ? `展開${label ? `「${label}」` : ""}` : `折疊${label ? `「${label}」` : ""}`;

  return (
    <div className="brief-section-card" data-testid="brief-section-card" data-block-id={blockId} data-collapsed={collapsed}>
      <button
        type="button"
        className="brief-section-card__toggle"
        aria-expanded={!collapsed}
        aria-label={buttonLabel}
        title={buttonLabel}
        onClick={toggle}
      >
        <span aria-hidden="true">{collapsed ? "▸" : "▾"}</span>
      </button>
      <div className="brief-section-card__body" hidden={collapsed}>
        {children}
      </div>
    </div>
  );
}
