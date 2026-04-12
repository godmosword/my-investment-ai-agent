import { useEffect, useMemo, useState } from "react";
import TerminalSymbolCard from "../components/TerminalSymbolCard";

const STORAGE_KEY = "qs_terminal_workspace_v1";
const DEFAULT_SYMBOLS = ["BTC", "SPY"];

function normalizeSymbol(raw) {
  return (raw ?? "").trim().toUpperCase();
}

function moveIndex(arr, from, to) {
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export default function Terminal() {
  const [symbols, setSymbols] = useState(DEFAULT_SYMBOLS);
  const [input, setInput] = useState("");
  const [dragIndex, setDragIndex] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        setSymbols([...new Set(parsed.map(normalizeSymbol).filter(Boolean))]);
      }
    } catch {
      // Ignore malformed local storage and keep default workspace.
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols));
  }, [symbols]);

  const canAdd = useMemo(() => {
    const s = normalizeSymbol(input);
    return !!s && !symbols.includes(s);
  }, [input, symbols]);

  const addSymbol = () => {
    const s = normalizeSymbol(input);
    if (!s || symbols.includes(s)) return;
    setSymbols((prev) => [...prev, s]);
    setInput("");
  };

  return (
    <>
      <div className="page-header">
        <div className="page-title">Terminal 工作區</div>
        <div className="page-subtitle">
          Launchpad 風格：可儲存 watchlist、拖曳重排、單一代號深度快照
        </div>
      </div>

      <div className="terminal-toolbar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="輸入代號（例：BTC、SPY、NVDA）"
          className="terminal-input"
          onKeyDown={(e) => {
            if (e.key === "Enter") addSymbol();
          }}
        />
        <button
          type="button"
          onClick={addSymbol}
          className="terminal-btn"
          disabled={!canAdd}
          style={{ opacity: canAdd ? 1 : 0.5 }}
        >
          加入
        </button>
        <button
          type="button"
          className="terminal-btn"
          onClick={() => setSymbols(DEFAULT_SYMBOLS)}
        >
          重設
        </button>
      </div>

      <div className="terminal-workspace-grid">
        {symbols.map((symbol, index) => (
          <div
            key={symbol}
            draggable
            onDragStart={() => setDragIndex(index)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              if (dragIndex == null || dragIndex === index) return;
              setSymbols((prev) => moveIndex(prev, dragIndex, index));
              setDragIndex(null);
            }}
          >
            <TerminalSymbolCard
              symbol={symbol}
              onRemove={() => setSymbols((prev) => prev.filter((s) => s !== symbol))}
              onMoveUp={() =>
                setSymbols((prev) => (index > 0 ? moveIndex(prev, index, index - 1) : prev))
              }
              onMoveDown={() =>
                setSymbols((prev) =>
                  index < prev.length - 1 ? moveIndex(prev, index, index + 1) : prev,
                )
              }
              dragHandleProps={{
                onMouseDown: () => setDragIndex(index),
              }}
            />
          </div>
        ))}
      </div>
    </>
  );
}
