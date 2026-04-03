# Staging：選幣／選股 Gate 閾值實驗

對齊 [`TODOS.md`](../TODOS.md) 橫切「閾值實驗」與 Priority **1**。

## 預設值（與 [`main.py`](../main.py) `_validate_env_types` 一致）

| 變數 | 預設 | 說明 |
|------|------|------|
| `PICK_ROTATION_OVERRIDE_MIN_GAP` | `12` | 同標延續最低分差門檻（浮點） |
| `PICK_REPEAT_MIN_SELECTION_SCORE` | `75` | 重複選標最低分數門檻 |
| `PICK_REPEAT_DAYS_MAX` | `2` | 連日重複上限（與 rotation 語意一併理解） |

`STRICT_PICK_ROTATION=0` 可關閉同標 rotation Gate（僅除錯／對照用，**不建議**長期 staging 關閉）。

## 建議操作

1. 在 **staging**（非生產頻道）**單變因**調整，每次只改一項：
   - 調高 `PICK_ROTATION_OVERRIDE_MIN_GAP`（例如 12 → 14）→ 較難「同日同標無理由延續」
   - 或暫緊 `PICK_REPEAT_MIN_SELECTION_SCORE`（例如 75 → 78）→ 提高重複選用門檻
2. 跑完整管線或至少雙 crew，記錄：
   - `validate_report` 是否通過
   - [`gate_failure_log`](../docs/SQL/gate_failure_weekly_summary.sql) 或本機 `.qsilicon/last_gate_failure/`（`GATE_FAILURE_ARTIFACTS`）
   - 主觀：日報是否仍「可讀、可執行、標的多樣性可接受」
3. **維持 3–5 個交易日**再換下一組參數，避免單日雜訊。
4. **回滾**：還原 env 為預設或上一組穩定值；staging 與 prod **分開**設定，勿直接試產線。

## 實驗紀錄表（可複製到內部文件）

| 日期 | 變更項 | 舊值→新值 | Gate 結果 | gate_failure（Y/N） | 備註 |
|------|--------|-----------|-----------|----------------------|------|
| | | | | | |

## 成功判準（建議）

- rotation／重複選用相關 **blocking** 在可接受頻率（例如 &lt; 每週 N 次，由團隊定義）
- 無明顯可讀性倒退（仍通過 HTML／新聞／QSREC 契約）
- 若啟用 `ADAPTIVE_GATE_THRESHOLDS=1`，可對照 [`adaptive_gate_thresholds.py`](../adaptive_gate_thresholds.py) 日誌與 BQ 聚合

## 與自適應門檻的銜接

[`adaptive_gate_thresholds.py`](../adaptive_gate_thresholds.py) 在 `ADAPTIVE_GATE_THRESHOLDS=1` 時可讀取 `gate_failure_log`（見該檔與 `ENV_TEMPLATE` 新增變數）；實驗數據可作為日後門檻調整與產品決策依據。

## 修訂紀錄

- **2026-04-04**：補預設值表、實驗紀錄表、回滾與成功判準。
