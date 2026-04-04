# Prompt／規則變更登記簿（人審後手動更新）

對齊 TODOS「Prompt 變更登記簿」：Gate 人審流程若決議修改 [`crew.py`](../crew.py) task 文字、[`validation_rules.py`](../validation_rules.py) 或 [`report_html_gates.py`](../report_html_gates.py)，請於此檔**追加一行**（或於 [`CHANGELOG.md`](../CHANGELOG.md) 同日條目加子項），便於稽核「**非**自動改 prompt」。

## 格式

`YYYY-MM-DD | 觸發摘要（可附 gate_failure fingerprint／issue 關鍵字） | 變更摘要 | PR／commit`

## 登記

| 日期 | 觸發 | 變更 | 追蹤 |
|------|------|------|------|
| 2026-04-04 | 投資解讀缺少當日量化數據引用／儀表對齊 | `crew.py` `_NEWS_FMT`：投資解讀數字須對同段區塊①儀表；禁儀表未列之精確報價。`validation_rules.py`：`NUMERIC_INVESTMENT_*` 允許 `投資解讀` 與冒號間空白（對齊 Telegram `<i>` 模板）。 | 本輪 |
| 2026-04-04 | 同上（機檢升格可選） | `report_html_gates.py`：`STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE=1` 時比對投資解讀數字與區塊① `<code>` 讀值；預設關閉。 | 本輪 |

## 修訂紀錄

- **2026-04-04**：建立本檔與表頭。
