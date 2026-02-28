from google.cloud import bigquery
from datetime import datetime, timezone, timedelta
import random

PROJECT_ID = "my-investment-ai-agent"


def inject_test_whale_data(n: int = 10) -> None:
    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.market_data.btc_whale_transactions"

    print(f"⏳ 準備產生 {n} 筆測試巨鯨數據...")

    base_time = datetime.now(timezone.utc)
    rows_to_insert = [
        {
            "timestamp": (base_time - timedelta(hours=random.uniform(0, 24))).isoformat(),
            "amount": round(random.uniform(100, 2500), 2),
        }
        for _ in range(n)
    ]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if not errors:
        print("✅ 成功！已將測試數據寫入 BigQuery。")
        print("👉 現在請回到 Streamlit 戰情室網頁，重新整理看看圖表！")
    else:
        print(f"❌ 寫入失敗，請檢查錯誤訊息: {errors}")


if __name__ == "__main__":
    inject_test_whale_data()
