import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const DESKTOP_BREAKPOINT = 768;
const CHORD_WINDOW_MS = 1500;

/**
 * Default chord registry for FE-5 desktop power features.
 * Keys are uppercase second-key codes; values are routes navigated to
 * after a `G` prefix within the chord window.
 */
const DEFAULT_CHORDS = {
  // 投資觀點（5 板塊收斂後的「日報」入口）
  B: "/insights",
  // 監控（FE-3 Portfolio › Monitor tab）
  M: "/portfolio?tab=monitor",
  // 設定
  S: "/settings",
};

function isEditableTarget(target) {
  if (!target) return false;
  const tag = String(target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.isContentEditable) return true;
  return false;
}

function isDesktopViewport() {
  if (typeof window === "undefined") return false;
  return window.innerWidth >= DESKTOP_BREAKPOINT;
}

/**
 * Desktop-only `G <X>` chord shortcuts. Mobile (`< 768px`) is a no-op.
 *
 * @param {Record<string, string>} [chords] — override the default chord map.
 */
export default function useKeyboardShortcuts(chords = DEFAULT_CHORDS) {
  const navigate = useNavigate();

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    if (!isDesktopViewport()) return undefined;

    let armedAt = 0;
    let timer = null;

    const disarm = () => {
      armedAt = 0;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const onKey = (e) => {
      if (isEditableTarget(e.target)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const key = (e.key || "").toUpperCase();

      if (armedAt && Date.now() - armedAt <= CHORD_WINDOW_MS && chords[key]) {
        e.preventDefault();
        const target = chords[key];
        disarm();
        navigate(target);
        return;
      }

      if (key === "G") {
        armedAt = Date.now();
        if (timer) clearTimeout(timer);
        timer = setTimeout(disarm, CHORD_WINDOW_MS);
        return;
      }

      // any other key cancels a pending chord
      if (armedAt) disarm();
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      disarm();
    };
  }, [chords, navigate]);
}
