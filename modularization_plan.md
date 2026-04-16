# Plan: 日報區塊模組化 (Brief Section Modularization)

## 閱讀地圖（建議順序）

1. **[目標：短／中／長期](#目標短期--中期--長期)** — 交付節奏與願景  
2. **[產品與交付原則](#產品與交付原則)** — 過渡期不影響日報產出、完成後組織級客製  
3. **[五個 Phase 總覽](#五個-phase-總覽)** — 實作主軸一頁表  
4. **[Phase 1–5 詳情與可切片任務](#phase-1模板原子化)** — 開發與 PR 切法  
5. **[架構三層與 Registry](#架構三層與-registry)** — Jinja2／程式／Gate  
6. **[版型與區塊行為](#版型與區塊行為)** — Profile、互動、Lite 版面、Gate 設計  
7. **[決策附錄](#附錄-a外部方案對照grok)** — Grok、一區塊一 Agent、時事多觀點  
8. **[Critical Files](#critical-files)**、**[Verification](#verification)**、**[NOT in Scope](#not-in-scope)**

---

## 背景與意圖

**Why:** 日報目前由單一 `telegram_report.j2`（約 263 行）+ 固定 `DailyBriefReport` schema 驅動；加區塊或改順序易牽動全檔，且每次 run 只有固定版面。

**產品動機:** 讀者與內部對**區塊組合、順序、主編 tone** 需求不同 → 模組化支援**客製差異化**，並讓**小組可擁有單一區塊**（PR 範圍縮小、討論與修改不必整份日報重構）。

**Intended outcome:** 以 **named profile**（`full` / `lite` / `crypto-only` 等）驅動有序 **block_id** 列表；每區塊獨立 Jinja2 macro；`validate_report` **profile-aware**；資料仍由既有 `assemble`／tools 注入（首階段不在區塊內第二套抓數）。語氣差異首階段靠 **Crew 提示詞 + profile 可見區塊**；每使用者即時選 tone 見 [NOT in Scope](#not-in-scope)。

**設計成熟度（內部評分）：** 概念由約 4/10 收斂至 **8/10**（區塊粒度、profile 開關、lite 內容、Gate 策略、掃讀 hint 已定）。

---

## 產品與交付原則

本節為 **產品／工程對齊用** 的成功定義：模組化 **過程中** 預設讀者無感；**完成後** 同一套引擎可支援 **組織級** 版型與區塊組合（非第二條獨立資料管線，除非另做產品決策）。

### 過渡期（模組化進行中）— 不影響日報產出

1. **預設路徑鎖定現行行為**：在 Phase 1 與 Phase 2 的 **`full` 等價**驗收通過前，**正式環境**只走與今日管線等價之組裝。若已引入 `REPORT_PROFILE`，**production 固定 `full`**（或由程式內預設 `full`，非必要不切換）。
2. **等價為合併門檻**：Phase 1 拆 macro 後須通過計畫內 **golden／byte-identical 或專案約定之 diff 收斂**，並搭配 `pytest -m smoke` 與 `validate_report`，避免空白、條件分支或縮排差異造成 Gate 或 Telegram 呈現漂移。
3. **新版型僅先離線驗證**：`lite`、`crypto-only`、可選 YAML layout、新區塊等，**不**在未驗證前綁定 production cron；僅 **staging／手動**或明確試驗排程啟用。
4. **單一資料管線**：模組化過程 **不** 改變既有 `assemble`／tools 注入契約；組織差異先落在 **模板／profile／組裝順序**，避免客觀數字與敘事來源與現行分叉（對齊專案「無數據幻覺」紅線）。

### 完成後 — 日報產出可組織級客製

於 Phase 2–4 落地並驗收後，組織可依下列機制差異化（細節見 [五個 Phase 總覽](#五個-phase-總覽)、[Phase 4](#phase-4擴充版型與配置驅動)）：

| 機制 | 作用 |
|------|------|
| **`REPORT_PROFILE`**（`full`／`lite`／`crypto-only`） | 選擇讀本厚度與區塊集合。 |
| **`BLOCK_REGISTRY`** + **`templates/blocks/*.j2`** | 區塊級責任邊界與替換，PR 範圍縮小。 |
| **可選 `config/brief_layouts/*.yaml`**（白名單） | 覆寫內建 `PROFILES` 的 block 順序與開關。 |
| **`validate_report(..., profile=)`**（Phase 3） | 避免 `lite` 被僅適用 `full` 之機構 Gate 誤擋。 |
| **BQ `profile` 欄位**（Phase 4） | 營運稽核各版型實際使用情形。 |

**仍非本計畫預設交付**：每使用者即時 tone、run 中切 profile、未經產品決策即擴充超過三個內建 profile 等 — 見 [NOT in Scope](#not-in-scope)。

---

## 目標：短期 / 中期 / 長期

| 時間軸 | 定義 | 目標 |
|--------|------|------|
| **短期** | Phase **1–2** 完成 | 模板切成可維護 macro；`REPORT_PROFILE` + `lite` 可跑；`full` 與重構前輸出 **等價**（byte-identical 或專案約定之 diff 收斂）；`BLOCK_REGISTRY` 與 `BLOCK_IDS` 一致可測。 |
| **中期** | Phase **3–4** 完成 | Gate 依 profile 跳過機構 Phase A/B/C（lite 等）；profile 區塊一致性檢查；`crypto-only`；可選 **YAML layout** 覆寫；BQ run log 帶 `profile`。 |
| **長期** | Phase **5** + 後續產品項 | **時事多觀點**區塊上線；再評估租戶級 layout、雙訊息（`DAILY_BRIEF_V2` Phase C）、per-user tone（需設定儲存）、音訊／TTS、非 Telegram 通道。 |

---

## 五個 Phase 總覽

| Phase | 名稱 | 核心交付 | 依賴 |
|:-----:|------|----------|------|
| **1** | 模板原子化 | `templates/blocks/*.j2` + 根模板僅組裝；行為不變 | 無 |
| **2** | 版型與組裝器 | `brief_profiles.py`、`BLOCK_REGISTRY`、`profiles/`、`render_telegram_daily_brief(profile)`、`REPORT_PROFILE`、`lite` | Phase 1 |
| **3** | Gate 與契約 | `validate_report(..., profile=)`、Phase A/B/C profile-aware、`_check_profile_block_consistency` | Phase 2 |
| **4** | 擴充版型與配置 | `crypto-only`、可選 `config/brief_layouts/*.yaml`、BQ `profile` | Phase 2–3 |
| **5** | 時事多觀點區塊 | `schemas` + crew／graph 單一產物 + `_current_affairs_roundtable.j2`、可選 Gate、`DAILY_BRIEF_V2` 小改版 | Phase 1–2（macro 槽位） |

---

## Phase 1：模板原子化

**目的：** 把 `telegram_report.j2` 拆成 **block macro 檔**，不改 HTML 語意、不改 assemble；利於小組平行改某一區。

**可切片 PR（範例順序，每片可獨立 review）：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 1a | 建立 `templates/blocks/`；抽 `_header.j2`、`_exec_summary.j2`；根模板 `import` 呼叫 | `pytest -m smoke` |
| 1b | 抽 `_market_mode.j2`、`_macro_framework.j2`、`_prediction_markets.j2` | 同上 |
| 1c | 抽 crypto 四段（dashboard／news／chatter／trades） | 同上 |
| 1d | 抽 AI 五段（bridge／dashboard／news／chatter／trades） | 同上 |
| 1e | 抽 `_institutional_view.j2`、`_previous_recs.j2`；**尾段**（partial tier／low_confidence／source health／QSREC）以 **`_footer_tail.j2`** 單一 macro **逐字複製**凍結基線（見下節「合併門檻」） | 同上 |
| 1f | 根 `telegram_report.j2`：**單行**匯入並依現順序呼叫 macro；全 CI smoke | **`REPORT_PROFILE` 尚未分流時，輸出與拆前等價**（見下節 **byte-identical** 測試） |

**合併門檻（Phase 1，已落地）：** [`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) 為凍結之 **Phase 0 單檔** Jinja（與拆 macro **前**之 `telegram_report.j2` 一致）；[`test_telegram_template_modularization.py`](test_telegram_template_modularization.py) 以相同 `telegram_render_context` 渲染 **modular 根模板** 與 **fixture**，斷言 **`==`（byte-identical）**；標記 **`pytest -m smoke`**。變更尾段空白語意時須**同步更新 fixture** 或調整 macro 使測試仍綠。

**目錄參考：**

```
templates/
  blocks/
    _header.j2 … _institutional_view.j2、_footer_tail.j2（尾段 verbatim）
    _current_affairs_roundtable.j2   # Phase 5 才接線；Phase 1 可建空壳或略過
```

---

## Phase 2：版型與組裝器

**目的：** **程式選模板** + 內建 **PROFILES** + **BLOCK_REGISTRY**（與 Gemini 對齊）；先支援 **`lite`** 與 **`full`**。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 2a | 新增 `brief_profiles.py`：`BLOCK_IDS`、`PROFILES`、`get_active_profile()` | 單元測試鍵名穩定 |
| 2b | `BLOCK_REGISTRY`：`block_id` → 模板路徑、macro 名、`empty_behavior`；**handler 不呼叫 LLM** | `BLOCK_IDS` 與 registry keys 一致測試 |
| 2c | `templates/profiles/telegram_full.j2`（= 現 full 組裝）與 `telegram_lite.j2` | lite 輸出行數顯著低於 full |
| 2d | `report_render.render_telegram_daily_brief(..., profile=)`；`main.py` 讀 `REPORT_PROFILE` | 預設 `full`；`lite` 可跑通 dry run |
| 2e | `test_brief_profiles.py`：full vs lite 結構／長度／必要區塊 | smoke + 新測 |

**環境變數：** `REPORT_PROFILE=lite|full|crypto-only`（`crypto-only` 可於 Phase 2 末尾或 Phase 4 再啟用模板檔，registry 可先登記）。

---

## Phase 3：Gate 與契約

**目的：** `validate_report` 認得 **profile**；機構 Phase A/B/C **僅在需要的 profile** 上生效；避免 lite 誤套 full 的 HTML 強檢。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 3a | `validate_report(text, *, profile="full")`；`_phase_a/b/c_gate_required(profile)` | 簽名與呼叫點更新 |
| 3b | `main.py` 傳 `profile` 進 validate | 整合測試 |
| 3c | `_check_profile_block_consistency(text, profile)` | lite 不含機構區時不報錯 |
| 3d | 測試：`REPORT_PROFILE=lite` + `STRICT_INSTITUTIONAL_PHASE_A_GATE=1` 不誤擋 | `pytest -m smoke` |

---

## Phase 4：擴充版型與配置驅動

**目的：** **`crypto-only`** profile；營運可選 **YAML layout** 覆寫（與內建 `PROFILES` merge）；**BQ** 記錄 `profile`。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 4a | `templates/profiles/telegram_crypto_only.j2` + `PROFILES["crypto-only"]` | 渲染測試 |
| 4b | `config/brief_layouts/README.md` + 範例 YAML；`BRIEF_LAYOUT_FILE=` 才 merge；block_id **白名單** | 無 env 與無檔案時行為同 Phase 2 |
| 4c | BQ run log（或既有表）新增 `profile` 欄位 | 可選與 `SKIP_BIGQUERY` 相容 |

---

## Phase 5：【時事多觀點】區塊（Podcast 型態文字）

**目的：** 新增可選區塊 **多角色文字對談**（非預設音訊）；結構化進 `DailyBriefReport`，經 macro 渲染。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 5a | `schemas.py` roundtable 結構；`BRIEF_CURRENT_AFFAIRS=1` 類開關 | Pydantic 測試 |
| 5b | `crew.py` 或 `graph/` **單一 task／子節點**產出（不採「每區塊一 Agent」預設） | 管線 smoke |
| 5c | `_current_affairs_roundtable.j2`；`BLOCK_REGISTRY` + `full` profile 選用；`assemble` 注入 | 數字與儀表板一致或 N/A |
| 5d | 可選 strict Gate；更新 `docs/DAILY_BRIEF_V2.md` 順序一句 | 文件 PR |

**紅線：** 對話內數字須對齊 tools／儀表板；HTML 僅白名單（見附錄 B）；**第 19 區塊**需與「18 區塊粗粒度」原則做一次設計取捨（ADR 可選）。

---

## 架構三層與 Registry

| Layer | 內容 |
|-------|------|
| **1** | `templates/blocks/_*.j2` — `{% macro %}`，同一 context |
| **2** | `brief_profiles.py`：`PROFILES`、`get_active_profile()`、`BLOCK_REGISTRY`；`templates/profiles/*.j2` |
| **3** | `report_html_gates.validate_report(..., profile=)`；profile-aware Phase A/B/C；區塊一致性 |

**Atomic Design 對應（Gemini）：** Atoms = macro 檔；Molecules = `include` 子切片；Organisms = `profiles/*.j2`。

**BLOCK_REGISTRY 鍵值範例意義：** `block_id` → `template_path`、`macro_name`、可選 **schema 綁定說明**（供除錯／Gate 擴充）、`empty_behavior`。Registry 可文件化 **CODEOWNERS／負責小組**。

**BLOCK_IDS（現行基線；Phase 5 再插入 roundtable）：**

```python
BLOCK_IDS = [
    "header", "exec_summary", "previous_recs", "market_mode",
    "macro_framework", "prediction_markets",
    "crypto_dashboard", "crypto_news", "crypto_chatter", "crypto_trades",
    "ai_bridge", "ai_dashboard", "ai_news", "ai_chatter", "ai_trades",
    "institutional_view", "source_health", "qsrec",
]
# Phase 5：可於 institutional_view 之後、source_health 前加入 "current_affairs_roundtable"
```

```python
PROFILES = {
    "full": BLOCK_IDS,
    "lite": ["header", "exec_summary", "market_mode", "crypto_trades", "ai_trades", "qsrec"],
    "crypto-only": [
        "header", "exec_summary", "market_mode", "macro_framework",
        "prediction_markets", "crypto_dashboard", "crypto_news",
        "crypto_chatter", "crypto_trades", "source_health", "qsrec",
    ],
}
```

---

## 版型與區塊行為

### Profiles（IA）

| Profile | 用途 |
|---------|------|
| `full` | 完整機構讀本 |
| `lite` | 約 40 行：header、exec_summary、market_mode、雙邊 trades、qsrec |
| `crypto-only` | Crypto desk（Phase 4 模板） |

### 掃讀順序 hint（per-profile）

- `full`：市場模式 → 儀表板 → 命題 → 交易  
- `lite`：市場模式 → 交易（跳儀表板／新聞）  
- `crypto-only`：市場模式 → 儀表板 → 新聞 → 交易  

### 區塊空狀態（節選）

| Block | 行為 |
|-------|------|
| exec_summary | 無則 omit |
| prediction_markets | 環境關閉或無資料則 omit |
| crypto_dashboard | 缺資料用占位列，不整段刪 |
| crypto_news | 符合既有 PARTIAL_NEWS 規則 |
| current_affairs_roundtable | env 關閉或無 schema 則 omit；lite 預設不載 |

### Lite 版面（Pass 6）

- 總行數 ≤ ~40；macro 支援 `mobile_compact`；exec_summary ≤3 點、每點 ≤40 字；交易敘事截斷 ≤60 字。
- **讀者節奏（lite）：** 開啟 → 立即判斷 risk on/off → 三點摘要 → 直跳交易卡（Bloomberg 式短報）。

### 風險控管（設計審查已納入）

1. **Over-modularization：** 基線 **18** 個粗粒度 block；`crypto_news` 與 `crypto_chatter` 版面仍相鄰；`current_affairs_roundtable` 為可選 **第 19** 塊，併區與否需 ADR。  
2. **Profile proliferation：** 上線先 **3** 種 profile；新增需產品與 Gate 影響評估。  
3. **分隔線：** `────────────` 維持 **≤4** 條／profile 模板。

### Gate 設計（程式片段意圖）

```python
def _phase_a_gate_required(profile: str) -> bool:
    return profile in ("full", "institutional") and _strict_institutional_phase_a()
# B/C 類推
```

```python
def validate_report(text: str, *, profile: str = "full") -> dict: ...
```

---

## 附錄 A：外部方案對照（Grok）

| 對齊點 | 本計畫 |
|--------|--------|
| Composer | `render_telegram_daily_brief` + `profiles/*.j2` |
| 多版型 | `PROFILES` + `REPORT_PROFILE` |

**糾偏：** 不用 `<pre>`；區塊內不重跑 tools（Phase 1–4）；Python class-per-section 不取代 Jinja 主路徑（長期可選實驗）。

---

## 附錄 B：一區塊一 Agent？

**定案：** 不預設每 macro 一 Agent；高創意區塊用 **單一結構化 task** 或 **小 subgraph**。擴 roleplay 須過：成本、延遲、`validate_report`、tools 契約。

---

## 附錄 C：時事多觀點（Podcast 型態文字）

- Block id：`current_affairs_roundtable`  
- 文字多觀點、白名單 HTML；音訊／TTS 不在本 plan  
- 見 [Phase 5](#phase-5時事多觀點區塊podcast-型態文字)

---

## Critical Files

| File | Phase |
|------|-------|
| `templates/telegram_report.j2` | 1 → 2（改為 profile 入口或 re-export） |
| `templates/blocks/*.j2` | 1 |
| `tests/fixtures/telegram_report_phase0_monolithic.j2` | 1（**等價凍結基線**；與 macro 化前單檔一致） |
| `test_telegram_template_modularization.py` | 1（**smoke** byte-identical gate） |
| `templates/profiles/telegram_*.j2` | 2、4 |
| `brief_profiles.py`（可選 `brief/block_registry.py`） | 2 |
| `config/brief_layouts/*.yaml` | 4 |
| `report_render.py` | 1（`build_telegram_jinja_env`／`telegram_render_context`）→ 2 |
| `report_html_gates.py` | 3 |
| `main.py` | 2–3 |
| `schemas.py` / `crew.py` / `graph/*` | 5 |
| `docs/DAILY_BRIEF_V2.md` | 5 |

---

## Verification

```bash
ruff check .
python3 -m pytest -m smoke -v
REPORT_PROFILE=full SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py   # 與重構前等價檢查
REPORT_PROFILE=lite SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py
REPORT_PROFILE=lite STRICT_INSTITUTIONAL_PHASE_A_GATE=1 python3 -m pytest -m smoke -v
```

---

## NOT in Scope

- Per-user profile／**即時主編 tone**（無設定儲存前）
- 每靜態區塊各一專屬 LLM Agent（預設架構）
- Email／web 同套模板（escape 規則不同）
- run 中切 profile
- 區塊級快取（與 tools cache 分開）
- launch 超過 **3** 個內建 profile（再擴需產品決策）
- 真實音訊 podcast 託管／TTS

---

## What Already Exists (Reuse)

- 條件渲染：`{% if crypto.exec_summary %}`、`PREDICTION_MARKETS_IN_BRIEF` 等  
- `tg_soft_wrap_mobile`（`report_render.py`）  
- `REPORT_TIER_PARTIAL_NEWS`  
- `_flatten_brief_text_for_na_gate()`（`report_render.py`）

---

## Optional：Pre-step（與模組化無硬依賴）

```bash
# 僅在維護策略要收斂 repo 體積時執行
git rm -r .claude/skills/gstack/
echo '.claude/skills/gstack/' >> .gitignore
```
