"""專案共用設定：PROJECT_ID、資料表名稱等。"""
import os

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "my-investment-ai-agent")
METRICS_TABLE = f"{PROJECT_ID}.market_data.daily_metrics"
WHALE_TABLE = f"{PROJECT_ID}.market_data.btc_whale_transactions"
RECOMMENDATIONS_TABLE = f"{PROJECT_ID}.market_data.trade_recommendations"
PAPER_TRADE_TABLE = RECOMMENDATIONS_TABLE
