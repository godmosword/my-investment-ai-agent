"""專案共用設定：PROJECT_ID、資料表名稱、LLM 模型 ID（LiteLLM）等。"""
import os


def _env_model(*env_keys: str, default: str) -> str:
    """依序讀取環境變數，取第一個非空白值；皆無則回傳 default。"""
    for k in env_keys:
        v = os.getenv(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def _env_flag(key: str, default: str = "0") -> bool:
    value = os.getenv(key, default)
    return str(value).strip().lower() in ("1", "true", "yes")


PROJECT_ID = os.getenv("GCP_PROJECT_ID", "my-investment-ai-agent")
METRICS_TABLE = f"{PROJECT_ID}.market_data.daily_metrics"
WHALE_TABLE = f"{PROJECT_ID}.market_data.btc_whale_transactions"
RECOMMENDATIONS_TABLE = f"{PROJECT_ID}.market_data.trade_recommendations"
PAPER_TRADE_TABLE = RECOMMENDATIONS_TABLE
LLM_RUN_LOG_TABLE = f"{PROJECT_ID}.market_data.llm_run_log"
GATE_FAILURE_LOG_TABLE = f"{PROJECT_ID}.market_data.gate_failure_log"
REVIEWER_LOG_TABLE = f"{PROJECT_ID}.market_data.reviewer_log"
# Web Push 持久化（T4a）：可選 BQ 表；見 docs/PWA_WEB_PUSH.md 與 `docs/SQL/web_push_subscriptions.sql`
WEB_PUSH_SUBSCRIPTIONS_TABLE = os.getenv(
    "WEB_PUSH_SUBSCRIPTIONS_TABLE",
    f"{PROJECT_ID}.market_data.web_push_subscriptions",
).strip()
# 實盤 BQ vs yfinance 觀測寫入（可選）；見 `scripts/symbol_price_probe.py`
PRICE_PROBE_LOG_TABLE = os.getenv("PRICE_PROBE_LOG_TABLE", "").strip()
# Paper execution 狀態轉移稽核（隊列 28a，可選 BQ）；空字串則略過寫入。DDL 見 docs/SQL/paper_execution_audit.sql
PAPER_EXECUTION_AUDIT_TABLE = os.getenv("PAPER_EXECUTION_AUDIT_TABLE", "").strip()

# LiteLLM 模型字串（crew fallback 鏈與 _API_KEY_MAP 依此比對）
MODEL_GROK = _env_model("MODEL_GROK", default="xai/grok-4-1-fast-reasoning")
# 相容舊慣例：OPENAI_MODEL 優先，其次 MODEL_GPT
MODEL_GPT = _env_model("OPENAI_MODEL", "MODEL_GPT", default="openai/gpt-4o-mini")
# Risk Critic + Quant Strategist 使用 Gemini 3 Flash（支援 thinking + structured outputs）
MODEL_GEMINI = _env_model("MODEL_GEMINI", default="gemini/gemini-3-flash-preview")
MODEL_CLAUDE = _env_model("MODEL_CLAUDE", default="anthropic/claude-sonnet-4-20250514")
# 文稿潤稿主編（Writing Editor）：輕量快速，僅做文字改寫
MODEL_GPT_NANO = _env_model("MODEL_GPT_NANO", default="openai/gpt-5.4-nano-2026-03-17")

# Phase 3 shadow switch: 1=run LangGraph engine, 0=legacy CrewAI path.
USE_LANGGRAPH_ENGINE = _env_flag("USE_LANGGRAPH_ENGINE", "1")
