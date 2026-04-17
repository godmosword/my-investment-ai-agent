# Brief layouts（Phase 4b）

可選 **YAML** 覆寫內建 `PROFILES` 的區塊**順序**（與 `brief_profiles.profile_block_ids()` 對齊）。**不設** `BRIEF_LAYOUT_FILE` 或檔案不存在時，行為與 Phase 2 相同（僅內建 profile）。

**重要（Phase 4d）：** 目前管線的 Telegram HTML 仍由 [`templates/profiles/`](../templates/profiles/) **靜態** Jinja 組裝；`profile_block_ids()` 的 merge 結果**不會**改變 `render_telegram_daily_brief` 輸出的區塊順序。YAML 適合營運／API 消費與未來「動態組版」接線；見根目錄 [`modularization_plan.md`](../modularization_plan.md#phase-4d)。

## 環境變數

| 變數 | 說明 |
|------|------|
| `BRIEF_LAYOUT_FILE` | 指向 YAML 的路徑。可為**專案根相對**（例如 `config/brief_layouts/example_lite_reorder.yaml`）或絕對路徑。未設定或空字串 → 不使用 layout。 |

## YAML 格式

根物件為 mapping，支援：

| 鍵 | 必填 | 說明 |
|----|------|------|
| `applies_to_profile` | 否 | 若設定，必須與目前 `REPORT_PROFILE`（或程式傳入的 profile）**字串一致**（不分大小寫）。不符時**整份 layout 忽略**，並寫 warning log。 |
| `blocks` | 使用 layout 時必填 | 字串陣列，每項為 **coarse block id**。每個 id 須同時在 **`BLOCK_IDS` 白名單**內，且屬於該 profile 內建列表的一員；**集合須與內建 profile 完全相同**（僅允許**重排**，不允許增刪 id，以免與現有 Jinja 靜態模板脫節）。 |

## 範例檔

- [`example_lite_reorder.yaml`](example_lite_reorder.yaml) — 在 `lite` 下將 `ai_trades` 排到 `crypto_trades` 之前（示範重排）。

## 營運注意

- 建議先在 **staging** 或離線管線驗證；見根目錄 [`modularization_plan.md`](../../modularization_plan.md)「產品與交付原則」。
- 無效 YAML（解析錯誤）會在呼叫 `profile_block_ids()` 時 **`ValueError`**，請在部署前用單元測試或手動載入驗證。
