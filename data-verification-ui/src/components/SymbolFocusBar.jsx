import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useSymbolFocus } from "../context/SymbolFocusContext";

/**
 * Cross-page strip: shared focus ticker (localStorage) + quick jump to Insights.
 */
export default function SymbolFocusBar({ compact = false }) {
  const { symbol, setSymbol } = useSymbolFocus();
  const [draft, setDraft] = useState(symbol || "");

  useEffect(() => {
    setDraft(symbol || "");
  }, [symbol]);

  const apply = () => {
    setSymbol(draft);
  };

  return (
    <div className={`symbol-focus-bar ${compact ? "symbol-focus-bar--compact" : ""}`}>
      <span className="symbol-focus-bar__label">關注代號</span>
      <input
        className="symbol-focus-bar__input"
        value={draft}
        onChange={(e) => setDraft(e.target.value.toUpperCase())}
        placeholder="例 BTC"
        maxLength={16}
        onKeyDown={(e) => {
          if (e.key === "Enter") apply();
        }}
      />
      <button type="button" className="terminal-btn" onClick={apply}>
        套用
      </button>
      {symbol ? (
        <button type="button" className="terminal-btn" onClick={() => { setSymbol(""); setDraft(""); }}>
          清除
        </button>
      ) : null}
      {symbol ? (
        <span className="symbol-focus-bar__active">
          目前：<strong>{symbol}</strong>
        </span>
      ) : (
        <span className="symbol-focus-bar__hint">未設定（各頁可獨立瀏覽）</span>
      )}
      <Link to="/insights" className="symbol-focus-bar__link">
        Insights →
      </Link>
    </div>
  );
}
