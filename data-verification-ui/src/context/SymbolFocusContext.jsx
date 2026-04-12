import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  useEffect,
} from "react";

const STORAGE_KEY = "qs_symbol_focus_v1";

const SymbolFocusContext = createContext(null);

export function SymbolFocusProvider({ children }) {
  const [symbol, setSymbolState] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed === "string" && parsed.trim()) {
        setSymbolState(parsed.trim().toUpperCase());
      }
    } catch {
      // ignore
    }
  }, []);

  const setSymbol = useCallback((raw) => {
    const next = (raw ?? "").trim().toUpperCase();
    setSymbolState(next);
    try {
      if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore quota / private mode
    }
  }, []);

  const value = useMemo(() => ({ symbol, setSymbol }), [symbol, setSymbol]);
  return (
    <SymbolFocusContext.Provider value={value}>{children}</SymbolFocusContext.Provider>
  );
}

export function useSymbolFocus() {
  const ctx = useContext(SymbolFocusContext);
  if (!ctx) {
    throw new Error("useSymbolFocus must be used within SymbolFocusProvider");
  }
  return ctx;
}
