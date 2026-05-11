# ADR：Tech pulse → investment-ai-agent（日報 exclusion 注入）

## 狀態

Accepted（2026-05-11）— Phase 1 採 **HTTP 只讀拉取**；共用 BigQuery 表列為 Phase 2 選項。

## 背景

第二 repo（tech-pulse／scoring）可能產出產業或敘事訊號；本 repo 日報管線 **嚴禁** 將非 Python 底層報價注入 `price_context`。允許路徑為：將 **經 API 取得之摘要文字** 併入 Crew 的 `exclude_context`（與 earnings focus 同層敘事約束），供模型參考，缺失時 **`[DATA_MISSING:…]`**。

## 決策

1. **Phase 1（本迭代）**：環境變數 **`TECH_PULSE_URL`**（HTTPS GET）。回應優先解析 JSON 的 **`summary`** 字串；否則使用 JSON 字串化子集或純文字 body（上限 8k 字元）。
2. **Phase 2（可選）**：若需離線批次或跨服務單一真實來源，再評估 **共用 BQ 表**（tech-pulse 寫入、本 repo 讀取）— 須另開 ADR 修訂 schema、IAM、頻率與 `SKIP_BIGQUERY` 行為。
3. **開關**：僅在 **`TECH_PULSE_IN_BRIEF=1`** 時呼叫；預設關閉，維持 production byte-identical 策略。
4. **CI／本機**：**`MOCK_APIS=1`** 時不發外網；回傳固定 **`[DATA_MISSING:tech_pulse_mock]`** 敘述（仍走 `_get_cache` / `_set_cache`）。
5. **快取**：`tools/tech_pulse_tool.py` 內 **TTL 300s**、鍵含 URL 前綴，避免日報連跑打爆上游。

## 後果

- 營運須保管 **`TECH_PULSE_URL`** 與上游 SLO；失敗時日報仍可走，區塊為 `DATA_MISSING`。
- 不引入新報價來源；**`fetch_symbol_quote` 等仍為唯一即時價格路徑**。

## 實作索引

- [`tools/tech_pulse_tool.py`](../tools/tech_pulse_tool.py)
- [`main.py`](../main.py) `trimmed_exclusion` 注入（earnings 之後）
- [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)
- [`test_tech_pulse_tool.py`](../test_tech_pulse_tool.py)
