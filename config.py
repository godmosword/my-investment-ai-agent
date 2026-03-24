"""專案共用設定：PROJECT_ID、資料表名稱、LLM 模型 ID（LiteLLM）等。"""
import os


def _env_model(*env_keys: str, default: str) -> str:
    """依序讀取環境變數，取第一個非空白值；皆無則回傳 default。"""
    for k in env_keys:
        v = os.getenv(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


PROJECT_ID = os.getenv("GCP_PROJECT_ID", "my-investment-ai-agent")
METRICS_TABLE = f"{PROJECT_ID}.market_data.daily_metrics"
WHALE_TABLE = f"{PROJECT_ID}.market_data.btc_whale_transactions"
RECOMMENDATIONS_TABLE = f"{PROJECT_ID}.market_data.trade_recommendations"
PAPER_TRADE_TABLE = RECOMMENDATIONS_TABLE

# LiteLLM 模型字串（crew fallback 鏈與 _API_KEY_MAP 依此比對）
MODEL_GROK = _env_model("MODEL_GROK", default="xai/grok-4-1-fast-reasoning")
# 相容舊慣例：OPENAI_MODEL 優先，其次 MODEL_GPT
MODEL_GPT = _env_model("OPENAI_MODEL", "MODEL_GPT", default="openai/gpt-4o-mini")
MODEL_GEMINI = _env_model("MODEL_GEMINI", default="gemini/gemini-2.5-pro")
MODEL_CLAUDE = _env_model("MODEL_CLAUDE", default="anthropic/claude-sonnet-4-20250514")
