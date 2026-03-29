# 邊界條件測試矩陣（Q-Silicon）

**目的**：盤點「邊界類型 × 模組 × 測試覆蓋 × 缺口 × 優先級」，與 [TODOS.md](../TODOS.md) 演進藍圖分離——本檔專注 **可驗證行為** 與 **回歸防線**。

**權威待辦**：仍為 [`TODOS.md`](../TODOS.md)。**戰報契約**：[`docs/DAILY_BRIEF_V2.md`](DAILY_BRIEF_V2.md)。**紅線**：[`CLAUDE.md`](../CLAUDE.md) §2。

---

## 圖例

| 欄位 | 說明 |
|------|------|
| **覆蓋** | 已有自動化測試或離線 fixture |
| **缺口** | 建議補測或僅人工／staging |
| **P** | P0＝合併前應覆蓋；P1＝nightly／full；P2＝可選 |

---

## 1. Gate／HTML 戰報（`validate_report`）

| 邊界類型 | 模組／入口 | 覆蓋 | 缺口 | P |
|----------|------------|------|------|---|
| 新聞則數不足／partial tier | `report_html_gates` | [`partial_news_ok`](../tests/fixtures/reports/partial_news_ok)、[`near_miss_five_tagged_news`](../tests/fixtures/reports/near_miss_five_tagged_news)、[`test_validate_report.py`](../test_validate_report.py) | 其餘 partial 邊界組合 | P1 |
| 儀表板／長度／QSREC 空 | `report_html_gates` | fixtures `invalid_*` | — | P0 |
| 輪動／score_gap 閾值 | `_pick_rotation_*` | `test_score_gap_boundary_11_fails`／`12_passes` | 其他 `PICK_ROTATION_*` env 組合 | P1 |
| 美股「本日選擇理由」長度 38／80、關鍵字計數 | `_pick_justification_equity_ok` | [`test_report_html_gates_boundaries.py`](../test_report_html_gates_boundaries.py)、[`near_miss_equity_pick_short`](../tests/fixtures/reports/near_miss_equity_pick_short) | — | P0 |
| `DATA_MISSING` 計數上限 | `DATA_MISSING_COUNT_GATE_MAX` | [`test_report_html_gates_boundaries.py`](../test_report_html_gates_boundaries.py)（含 blocking 前綴對齊） | — | P1 |
| 新聞新鮮度（錨定日） | `STRICT_NEWS_FRESHNESS_GATE` | [`test_news_freshness.py`](../test_news_freshness.py) | 與 `PIPELINE_REPORT_DATE` 組合矩陣 | P1 |
| Telegram HTML 白名單／平衡 | `telegram_sender` | [`test_critical_paths.py`](../test_critical_paths.py) `TestTelegramSanitization` | 超長巢狀、`&` 邊界已部分覆蓋 | P0 |
| 結構化 Pydantic | `schemas.py` | [`test_validate_report.py`](../test_validate_report.py) structured 區塊 | 欄位缺省與邊界值表驅動 | P2 |

---

## 2. 環境變數與啟動

| 邊界類型 | 模組 | 覆蓋 | 缺口 | P |
|----------|------|------|------|---|
| 必填金鑰缺失 | `main._validate_required_keys` | [`test_critical_paths.py`](../test_critical_paths.py) | 非法字元／空白 key | P2 |
| `PIPELINE_STRICT_ENV` | `_validate_critical_env_strict` | [`test_critical_paths.py`](../test_critical_paths.py) | Telegram off + BQ off 組合 | P1 |
| 數值型 env 無效 | `_validate_env_types` | [`test_critical_paths.py`](../test_critical_paths.py) | 完整 env 名稱表逐一 bad value | P2 |

---

## 3. HTTP／工具層（無幻覺數據）

| 邊界類型 | 模組 | 覆蓋 | 缺口 | P |
|----------|------|------|------|---|
| JSON decode 失敗 | `tools_cache_http._response_json_dict` | [`test_tools_http_contract.py`](../test_tools_http_contract.py) | list 變體、空 body | P0 |
| Timeout／連線錯誤 | `_http_get` mock | 同上 | 429 + Retry-After（若上層有 sleep 則 mock time） | P1 |
| 快取驅逐 | `_set_cache` at max size | [`test_critical_paths.py`](../test_critical_paths.py) | 多 key TTL 過期競態 | P2 |

---

## 4. 管線併發與失敗（`main._run_pipeline_once`）

| 邊界類型 | 行為 | 覆蓋 | 缺口 | P |
|----------|------|------|------|---|
| Crypto `run()` 先拋錯 | `future_crypto.result()` 拋出，不組裝 | [`test_main_pipeline_boundaries.py`](../test_main_pipeline_boundaries.py) `_run_pipeline_once` | `run_pipeline_with_retries` → `execution_error_report` finalize（spy） | P0 |
| AI `run()` 拋錯 | 第二個 `result()` 拋出 | 可沿用 selective `ThreadPoolExecutor` 擴充 slot 邏輯 | — | P1 |
| Prewarm 單工具失敗 | 記 warning、不中斷 | [`main` prewarm loop] | 單測 mock tool raise | P2 |

---

## 5. CI 分層

| Marker | 用途 |
|--------|------|
| `smoke` | PR quick（現狀） |
| `boundary` | 邊界／契約（HTTP、`main` 雙 crew 失敗、Gate 門檻等）；**full／nightly** 的 `pytest -v` 會一併執行 |
| `slow` | 屬性測試等較重案例（例：[`test_boundary_hypothesis.py`](../test_boundary_hypothesis.py)）；可 `pytest -m "not slow"` 本機略過 |

選跑邊界子集：`pytest -m boundary -q`。

---

## 6. 修訂紀錄

- **2026-03-29**：初版；對齊「邊界條件精進計畫」Phase A–E。
- **2026-03-29**：補 `boundary`／`slow` marker、main 管線 finalize 斷言、Hypothesis（`sanitize_telegram_html`）、矩陣與 HTTP／Gate 覆蓋欄更新。
