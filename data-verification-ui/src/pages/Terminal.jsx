import { useEffect, useMemo, useState, useCallback } from "react";
import TerminalSymbolCard from "../components/TerminalSymbolCard";
import ExecutionIntentsBlotter from "../components/ExecutionIntentsBlotter";
import SymbolFocusBar from "../components/SymbolFocusBar";
import { useSymbolFocus } from "../context/SymbolFocusContext";

const STORAGE_V1 = "qs_terminal_workspace_v1";
const STORAGE_V2 = "qs_terminal_workspace_v2";

const DEFAULT_SYMBOLS = ["BTC", "SPY"];

const WORKSPACE_TEMPLATES = [
  { id: "crypto_core", label: "Crypto 核心", symbols: ["BTC", "ETH", "SOL"] },
  { id: "us_broad", label: "美股大盤", symbols: ["SPY", "QQQ", "IWM"] },
  { id: "ai_chain", label: "AI 鏈", symbols: ["NVDA", "AMD", "SMCI"] },
];

function normalizeSymbol(raw) {
  return (raw ?? "").trim().toUpperCase();
}

function newId(prefix = "g") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function moveIndex(arr, from, to) {
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function defaultWorkspace() {
  const gid = newId("g");
  return {
    version: 2,
    groups: [{ id: gid, name: "預設", symbols: [...DEFAULT_SYMBOLS] }],
    activeGroupId: gid,
  };
}

function migrateV1ToV2(rawV1) {
  try {
    const parsed = JSON.parse(rawV1);
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    const symbols = [...new Set(parsed.map(normalizeSymbol).filter(Boolean))];
    const gid = newId("g");
    return {
      version: 2,
      groups: [{ id: gid, name: "預設", symbols: symbols.length ? symbols : [...DEFAULT_SYMBOLS] }],
      activeGroupId: gid,
    };
  } catch {
    return null;
  }
}

export default function Terminal() {
  const { symbol: globalSymbol } = useSymbolFocus();
  const [workspace, setWorkspace] = useState(() => defaultWorkspace());
  const [input, setInput] = useState("");
  const [dragIndex, setDragIndex] = useState(null);
  const [newGroupName, setNewGroupName] = useState("");

  useEffect(() => {
    try {
      const raw2 = localStorage.getItem(STORAGE_V2);
      if (raw2) {
        const w = JSON.parse(raw2);
        if (w?.version === 2 && Array.isArray(w.groups) && w.groups.length > 0) {
          const groups = w.groups.map((g) => ({
            id: g.id || newId("g"),
            name: (g.name || "分組").slice(0, 32),
            symbols: Array.isArray(g.symbols)
              ? [...new Set(g.symbols.map(normalizeSymbol).filter(Boolean))]
              : [],
          }));
          let activeId = w.activeGroupId;
          if (!groups.some((g) => g.id === activeId)) activeId = groups[0].id;
          setWorkspace({ version: 2, groups, activeGroupId: activeId });
          return;
        }
      }
      const raw1 = localStorage.getItem(STORAGE_V1);
      if (raw1) {
        const migrated = migrateV1ToV2(raw1);
        if (migrated) {
          setWorkspace(migrated);
          localStorage.setItem(STORAGE_V2, JSON.stringify(migrated));
        }
      }
    } catch {
      // keep default
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_V2, JSON.stringify(workspace));
    } catch {
      // ignore
    }
  }, [workspace]);

  const activeGroup = useMemo(
    () => workspace.groups.find((g) => g.id === workspace.activeGroupId) ?? workspace.groups[0],
    [workspace],
  );

  const symbols = activeGroup?.symbols ?? [];

  const updateActiveGroup = useCallback((fn) => {
    setWorkspace((prev) => {
      const gid = prev.activeGroupId;
      const groups = prev.groups.map((g) => {
        if (g.id !== gid) return g;
        const next = fn(g);
        return { ...g, ...next };
      });
      return { ...prev, groups };
    });
  }, []);

  const setSymbolsForActive = useCallback(
    (nextSymbols) => {
      updateActiveGroup(() => ({ symbols: nextSymbols }));
    },
    [updateActiveGroup],
  );

  const canAdd = useMemo(() => {
    const s = normalizeSymbol(input);
    return !!s && !symbols.includes(s);
  }, [input, symbols]);

  const addSymbol = () => {
    const s = normalizeSymbol(input);
    if (!s || symbols.includes(s)) return;
    setSymbolsForActive([...symbols, s]);
    setInput("");
  };

  const addGlobalToActive = () => {
    const s = normalizeSymbol(globalSymbol);
    if (!s || symbols.includes(s)) return;
    setSymbolsForActive([...symbols, s]);
  };

  const addGroup = () => {
    const name = (newGroupName || `分組 ${workspace.groups.length + 1}`).trim().slice(0, 32);
    const gid = newId("g");
    setWorkspace((prev) => ({
      ...prev,
      groups: [...prev.groups, { id: gid, name, symbols: [] }],
      activeGroupId: gid,
    }));
    setNewGroupName("");
  };

  const removeGroup = (id) => {
    setWorkspace((prev) => {
      if (prev.groups.length <= 1) return prev;
      const groups = prev.groups.filter((g) => g.id !== id);
      let activeGroupId = prev.activeGroupId;
      if (activeGroupId === id) activeGroupId = groups[0].id;
      return { ...prev, groups, activeGroupId };
    });
  };

  const applyTemplateToActive = (template) => {
    const list = template.symbols.map(normalizeSymbol).filter(Boolean);
    if (!list.length) return;
    setSymbolsForActive([...new Set(list)]);
  };

  const addGroupFromTemplate = (template) => {
    const list = [...new Set(template.symbols.map(normalizeSymbol).filter(Boolean))];
    const gid = newId("g");
    setWorkspace((prev) => ({
      ...prev,
      groups: [...prev.groups, { id: gid, name: template.label, symbols: list.length ? list : [...DEFAULT_SYMBOLS] }],
      activeGroupId: gid,
    }));
  };

  const resetAll = () => {
    const w = defaultWorkspace();
    setWorkspace(w);
    try {
      localStorage.removeItem(STORAGE_V1);
    } catch {
      // ignore
    }
  };

  return (
    <>
      <div className="page-header">
        <div className="page-title">Terminal 工作區</div>
        <div className="page-subtitle">
          v2：多分組、一鍵模板、拖曳重排；與「關注代號」條同步（localStorage）
        </div>
      </div>

      <SymbolFocusBar compact />

      <ExecutionIntentsBlotter />

      <div className="terminal-workspace-tabs" role="tablist" aria-label="工作區分組">
        {workspace.groups.map((g) => (
          <button
            key={g.id}
            type="button"
            role="tab"
            aria-selected={g.id === workspace.activeGroupId}
            className={`terminal-workspace-tab ${g.id === workspace.activeGroupId ? "terminal-workspace-tab--active" : ""}`}
            onClick={() => setWorkspace((p) => ({ ...p, activeGroupId: g.id }))}
          >
            {g.name}
            <span className="terminal-workspace-tab__count">{g.symbols.length}</span>
          </button>
        ))}
      </div>

      <div className="terminal-toolbar terminal-toolbar--wrap">
        <input
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
          placeholder="新分組名稱（可選）"
          className="terminal-input terminal-input--narrow"
        />
        <button type="button" className="terminal-btn" onClick={addGroup}>
          新增分組
        </button>
        {workspace.groups.length > 1 ? (
          <button
            type="button"
            className="terminal-btn terminal-btn-danger"
            onClick={() => removeGroup(workspace.activeGroupId)}
          >
            刪除目前分組
          </button>
        ) : null}
      </div>

      <div className="terminal-template-row">
        <span className="terminal-template-label">模板</span>
        {WORKSPACE_TEMPLATES.map((t) => (
          <span key={t.id} className="terminal-template-actions">
            <button type="button" className="terminal-btn terminal-btn--small" onClick={() => applyTemplateToActive(t)}>
              套用「{t.label}」
            </button>
            <button type="button" className="terminal-btn terminal-btn--small" onClick={() => addGroupFromTemplate(t)}>
              ＋分組
            </button>
          </span>
        ))}
      </div>

      <div className="terminal-toolbar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="加入代號至「目前分組」"
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
        {globalSymbol && !symbols.includes(normalizeSymbol(globalSymbol)) ? (
          <button type="button" className="terminal-btn" onClick={addGlobalToActive} title={globalSymbol}>
            加入關注 {globalSymbol}
          </button>
        ) : null}
        <button type="button" className="terminal-btn" onClick={() => setSymbolsForActive([...DEFAULT_SYMBOLS])}>
          目前分組重設為預設
        </button>
        <button type="button" className="terminal-btn terminal-btn-danger" onClick={resetAll}>
          重設全部
        </button>
      </div>

      <div className="terminal-workspace-grid">
        {symbols.map((symbol, index) => (
          <div
            key={`${workspace.activeGroupId}-${symbol}`}
            draggable
            onDragStart={() => setDragIndex(index)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              if (dragIndex == null || dragIndex === index) return;
              setSymbolsForActive(moveIndex(symbols, dragIndex, index));
              setDragIndex(null);
            }}
          >
            <TerminalSymbolCard
              symbol={symbol}
              onRemove={() => setSymbolsForActive(symbols.filter((s) => s !== symbol))}
              onMoveUp={() =>
                setSymbolsForActive(index > 0 ? moveIndex(symbols, index, index - 1) : symbols)
              }
              onMoveDown={() =>
                setSymbolsForActive(
                  index < symbols.length - 1 ? moveIndex(symbols, index, index + 1) : symbols,
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
