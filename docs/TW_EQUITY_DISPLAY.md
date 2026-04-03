# 台股／非美股顯示（Pri 9 前置）

對齊 TODOS「台股 `$` 前綴」與 `asset_market` 枚舉。

## 結構化契約

- [`schemas.py`](../schemas.py) `ExecutableTradeLeg.asset_market`、`TradeRecommendation.asset_market` 可選 `US`／`TW`／`CRYPTO`。
- `None`：沿用區塊慣例（加密 crew → CRYPTO；AI 段 → US）。

## 模板與 render

- 現行 [`templates/telegram_report.j2`](../templates/telegram_report.j2) 仍統一在資產前加 `$`；**正式支援台股**時應依 `asset_market==TW` 改用 `NT$` 或純數字地域慣例（產品定稿後實作）。
- [`report_render.py`](../report_render.py) 可集中 `_format_asset_display(leg)`（未來補）。

## 修訂紀錄

- **2026-04-04**：初版；欄位已入 schema，模板行為待產品確認後改。
