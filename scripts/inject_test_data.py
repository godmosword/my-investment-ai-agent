"""一次性腳本：向 BigQuery 寫入測試用巨鯨交易列。

執行（專案根目錄）::

    python scripts/inject_test_data.py

需已設定 Application Default Credentials 或 GOOGLE_APPLICATION_CREDENTIALS。
專案 ID 取自 config.PROJECT_ID（與管線一致）。
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from google.cloud import bigquery  # noqa: E402

from config import PROJECT_ID  # noqa: E402


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
