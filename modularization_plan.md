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

## 當前進度快照（2026-04-27）

| Phase | 狀態 | 關鍵交付 |
|:-----:|:----:|----------|
| **1** 模板原子化 | ✅ 已落地（2026-04-26） | `templates/blocks/*.j2`；[`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) **byte-identical** smoke |
| **2** 版型與組裝器 | ✅ 已落地（2026-04-27） | [`brief_profiles.py`](brief_profiles.py)（`BLOCK_IDS`／`PROFILES`／`BLOCK_REGISTRY`）、`templates/profiles/telegram_{full,lite}.j2`、`REPORT_PROFILE` env、`render_telegram_daily_brief(..., profile=)` |
| **3** Gate 與契約 | ✅ 已落地（2026-04-27） | [`report_html_gates.py`](report_html_gates.py) `validate_report(..., profile=)`、Phase A/B/C profile-aware、`_check_profile_block_consistency`、[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py) |
| **4a** `crypto-only` | ✅ 已落地（2026-04-27） | [`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2)、`PROFILES["crypto-only"]`、Gate／一致性 |
| **4b** YAML layout 覆寫 | ✅ 已落地（2026-04-27） | [`brief_profiles_layout.py`](brief_profiles_layout.py)、`profile_block_ids` merge、[`config/brief_layouts/`](config/brief_layouts/)、`BRIEF_LAYOUT_FILE` env、`PyYAML` |
| **4c** BQ `profile` | ✅ 已落地（2026-04-16） | [`bigquery_writer.py`](bigquery_writer.py) `write_llm_run_log`／`write_gate_failure_log`、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql) |
| **5** 時事多觀點區塊 | 🟡 **下一步** | 見 [Phase 5 執行計畫（Next Step）](#phase-5-執行計畫next-step) |

> 預設仍 `REPORT_PROFILE=full`，與 Phase 0 凍結基線 **byte-identical**；生產行為零漂移。細節對應 [`CHANGELOG.md`](CHANGELOG.md)（2026-04-16／2026-04-26／2026-04-27）、[`TODOS.md`](TODOS.md) 「同步狀態」段。

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
| 2a | 新增 `brief_profiles.py`：`BLOCK_IDS`、`PROFILES`、`get_active_profile()` | 單元測試鍵名穩定（**已落地**，見 [`brief_profiles.py`](brief_profiles.py)、[`test_brief_profiles.py`](test_brief_profiles.py)） |
| 2b | `BLOCK_REGISTRY`：`block_id` → 模板路徑、macro 名、`empty_behavior`；**handler 不呼叫 LLM** | `BLOCK_IDS` 與 registry keys 一致測試（**已落地**） |
| 2c | `templates/profiles/telegram_full.j2`（= 現 full 組裝）與 `telegram_lite.j2` | lite 輸出行數顯著低於 full（**已落地**；`full` 仍 **byte-identical** 至 Phase 0 fixture） |
| 2d | `report_render.render_telegram_daily_brief(..., profile=)`；**`REPORT_PROFILE`** env | 預設 `full`；`lite` 可渲染（**已落地**；`main.py` 透過 env 傳遞即可） |
| 2e | `test_brief_profiles.py`：full vs lite 結構／長度／必要區塊 | smoke + 新測（**已落地**） |

**環境變數：** `REPORT_PROFILE=lite|full|crypto-only`（`crypto-only` 模板與 Gate 於 **Phase 4a** 啟用；registry 見 [`brief_profiles.py`](brief_profiles.py)）。

---

## Phase 3：Gate 與契約

**目的：** `validate_report` 認得 **profile**；機構 Phase A/B/C **僅在需要的 profile** 上生效；避免 lite 誤套 full 的 HTML 強檢。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 3a | `validate_report(text, *, profile="full")`；lite 時跳過機構 Phase A/B/C HTML 檢查 | **已落地**（[`report_html_gates.py`](report_html_gates.py)；回傳含 **`profile`**） |
| 3b | `main.py` 傳 `profile` 進 `validate_report`／`render_telegram_daily_brief`；`_validate_report_candidate` 同步 | **已落地**（[`main.py`](main.py)） |
| 3c | `_check_profile_block_consistency(text, profile)` | **已落地**（lite 誤用 full HTML 時 blocking） |
| 3d | 測試：`REPORT_PROFILE=lite` + `STRICT_INSTITUTIONAL_PHASE_A/B/C_GATE=1` 不誤擋 | **已落地**（[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)，`pytest -m smoke`） |

---

## Phase 4：擴充版型與配置驅動

**目的：** **`crypto-only`** profile；營運可選 **YAML layout** 覆寫（與內建 `PROFILES` merge）；**BQ** 記錄 `profile`。

**可切片任務：**

| 切片 | 內容 | 驗收 |
|------|------|------|
| 4a | `templates/profiles/telegram_crypto_only.j2` + `PROFILES["crypto-only"]` | **已落地**（[`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2)、[`brief_profiles.py`](brief_profiles.py) `telegram_profile_template_relpath`；[`report_html_gates.py`](report_html_gates.py) `crypto-only` Gate／一致性；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py) smoke） |
| 4b | `config/brief_layouts/README.md` + 範例 YAML；`BRIEF_LAYOUT_FILE=` 才 merge；block_id **白名單** | **已落地**（[`brief_profiles_layout.py`](brief_profiles_layout.py)、[`brief_profiles.py`](brief_profiles.py) `profile_block_ids`；[`config/brief_layouts/`](config/brief_layouts/)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；[`test_brief_profiles_layout.py`](test_brief_profiles_layout.py)；無 env／缺檔與 Phase 2 同） |
| 4c | BQ run log（或既有表）新增 `profile` 欄位 | **已落地**（[`bigquery_writer.py`](bigquery_writer.py) `write_llm_run_log`／`write_gate_failure_log`；[`main.py`](main.py)；[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)；`SKIP_BIGQUERY=1` 仍略過） |

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

### Phase 5 執行計畫（Next Step）

> 目標：**不破壞 `full` byte-identical 基線**的前提下，新增可選 **〔時事多觀點〕** 區塊；預設 `BRIEF_CURRENT_AFFAIRS=0`（關閉），開啟時由 Registry + macro 注入到 `full` profile 尾段（【機構速讀】之前）。

#### PR 切片與檔案地圖

**PR-5a｜Schema + Feature Flag（純新增，零行為變更）**

- 新增 `schemas.py` 內：
  - `RoundtableVoice`（`role: Literal["宏觀", "加密", "股票策略", "風險"]`、`viewpoint: str`、`evidence_anchor: str | None`、`disagreement: str | None`）。
  - `CurrentAffairsRoundtable`（`topic: str`、`voices: list[RoundtableVoice]`（**2–4 條**）、`consensus: str | None`、`unresolved: list[str]`、`dashboard_anchors: list[str]`（對應區塊① `<code>` 讀值 key，如 `"VIX"`、`"BTC_RSI14_1d"`））。
  - `DailyBriefReport.current_affairs_roundtable: CurrentAffairsRoundtable | None = None`（Optional，預設 `None`）。
- `ENV_TEMPLATE.txt` 新增 `BRIEF_CURRENT_AFFAIRS=0`（0/1）、`CURRENT_AFFAIRS_MAX_VOICES=4`、`CURRENT_AFFAIRS_MIN_VOICES=2`。
- 驗收：`python3 -m pytest -m smoke` 綠；新增 `test_current_affairs_schema.py`（**PR-5a 必含 TDD**）。

**PR-5b｜Crew/Graph 產出節點（單一 task，不新增 Agent）**

- **預設路徑（Crew）**：`crew.py` 增加 `current_affairs_roundtable_task`，掛在現有 **Editor/Judge 前**；prompt 要求：
  - 每個 voice 必須引用區塊① 儀表板中一個 `<code>` 讀值（填入 `evidence_anchor`）或明確 `N/A`。
  - 至少 1 條 `disagreement`；`consensus`＋`unresolved` 二選一非空。
  - 禁止 LLM 推導客觀數值（維持 `.cursorrules` §1 紅線）。
- **可選路徑（LangGraph）**：`graph/graph_nodes.py` 新增 `current_affairs_node`，接在 `Deep` 之後、`Formatter` 之前。`USE_LANGGRAPH_ENGINE=1` 時走此路徑。
- `crew_output_parse.py` 延伸至 `current_affairs_roundtable` 欄位；解析失敗 → 該欄位設 `None`，**不**阻擋報告。
- 驗收：`pytest -m smoke` 綠；`SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 BRIEF_CURRENT_AFFAIRS=1 python main.py` 乾跑產出 HTML 含〔時事多觀點〕段。

**PR-5c｜Block Macro + Registry 掛載**

- 新增 `templates/blocks/_current_affairs_roundtable.j2`：
  ```jinja
  {% macro render_current_affairs_roundtable(r) %}
  {% if r and r.voices %}
  <b>〔時事多觀點〕{{ r.topic | e }}</b>
  {% for v in r.voices %}
  <blockquote>
    <b>{{ v.role | e }}</b>：{{ v.viewpoint | e }}
    {% if v.evidence_anchor %}（錨點：<code>{{ v.evidence_anchor | e }}</code>）{% endif %}
    {% if v.disagreement %}<i>分歧：{{ v.disagreement | e }}</i>{% endif %}
  </blockquote>
  {% endfor %}
  {% if r.consensus %}<b>共識</b>：{{ r.consensus | e }}{% endif %}
  {% if r.unresolved %}<b>未決</b>：{{ r.unresolved | join("；") | e }}{% endif %}
  {% endif %}
  {% endmacro %}
  ```
- `brief_profiles.py`：
  - `BLOCK_IDS` 新增 `"current_affairs_roundtable"`。
  - `BLOCK_REGISTRY["current_affairs_roundtable"] = _current_affairs_roundtable.j2:render_current_affairs_roundtable`。
  - `PROFILES["full"].block_ids` 尾段（**機構速讀前**）條件加入：`if os.getenv("BRIEF_CURRENT_AFFAIRS") == "1"`。
  - `lite` 與 `crypto-only` **不** 納入（維持瘦身精神）。
- `report_render.py`：`assemble_daily_brief_report` 將 crew 解析後的 `current_affairs_roundtable` 注入 `DailyBriefReport`。
- 驗收：
  - `BRIEF_CURRENT_AFFAIRS=0` 時 **full profile byte-identical** 與 Phase 0 fixture（smoke 必測）。
  - `BRIEF_CURRENT_AFFAIRS=1` 時模板渲染非空、HTML 標籤僅用白名單（`<b>`／`<i>`／`<code>`／`<blockquote>`）。

**PR-5d｜可選 Strict Gate + 文件**

- `report_html_gates.py` 新增可選 gate：`STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1` 時：
  - HTML 需含「〔時事多觀點〕」標題、voice 數介於 `[MIN, MAX]`、每個 voice 至少一個 `<blockquote>`。
  - 結構化驗證 `current_affairs_roundtable.voices` 中至少 1 條 `disagreement` 非空；每個 `evidence_anchor` 如非 `None` 須命中 `dashboard_anchors` 白名單。
  - profile `lite`／`crypto-only`：**跳過**（與 4a 一致策略）。
- 文件：
  - `docs/DAILY_BRIEF_V2.md` 第四大區塊順序補一句：「〔時事多觀點〕（選用，`BRIEF_CURRENT_AFFAIRS=1`，置於機構速讀之前）」。
  - `CLAUDE.md` §6「Observability & Gates」新增一行 gate 描述。
  - `CHANGELOG.md` + `TODOS.md`（雙向對齊）記錄 Phase 5 落地日期與 env。
  - `README.md`「日報模組化」段將 Phase 5 從「仍待」移至「已交付」。
- 驗收：`ruff check .` + `pytest -m smoke` + `pytest -m boundary` 綠；nightly full suite 綠。

#### 紅線重申（`.cursorrules` §1、§2；本檔附錄 B）

1. **數字對齊**：每個 voice 若引用客觀值必須來自 `tools.py` 儀表板 context（`evidence_anchor` 白名單），**嚴禁** LLM 自行推導。
2. **HTML 白名單**：僅 `<b>`／`<i>`／`<u>`／`<s>`／`<code>`／`<blockquote>`／`<a>`；`telegram_sender.py` sanitization 已涵蓋，新 macro 禁用其他標籤。
3. **Thread safety**：新 crew task 沿用既有 `ThreadPoolExecutor` 語意，**不** 引入共享可變狀態。
4. **不擴張成「每區塊一 Agent」**：維持 Phase 5 原則——**單一 task／子節點**產出整個 roundtable；維持 18 區塊粗粒度。

#### 風險與決策點（建議開 ADR：`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`）

- **Token 成本**：+1 task；預估 <10% 成本漂移 — 靠 `COST_PER_MODEL.md` 實測複核。
- **LLM 幻覺風險**：以 `evidence_anchor` 白名單 + strict gate 收斂；gate 預設關閉，分階啟用。
- **Podcast 音訊**：**不在** Phase 5 範圍（仍是文字型態對談）；音訊生成留給後續 RFC。

#### 驗收指令速查

```bash
# 基線（關閉新區塊）— 必須 byte-identical
BRIEF_CURRENT_AFFAIRS=0 REPORT_PROFILE=full \
  python3 -m pytest -m smoke test_telegram_template_modularization.py -v

# 啟用新區塊乾跑
BRIEF_CURRENT_AFFAIRS=1 SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py

# Strict gate 回歸
STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1 BRIEF_CURRENT_AFFAIRS=1 \
  python3 -m pytest test_validate_report_current_affairs.py -v
```

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
| `test_brief_profiles.py` | 2 |
| `config/brief_layouts/*.yaml` | 4 |
| `report_render.py` | 1–2（`build_telegram_jinja_env`／`telegram_render_context`／`render_telegram_daily_brief(..., profile=)`） |
| `report_html_gates.py` | 3（`validate_report(..., profile=)`、lite 放寬、`_check_profile_block_consistency`） |
| `test_validate_report_profile_phase3.py` | 3 |
| `main.py` | 2–3 |
| `schemas.py` / `crew.py` / `graph/*` | 5 |
| `docs/DAILY_BRIEF_V2.md` | 5 |

---

## Verification

```bash
ruff check .
python3 -m pytest -m smoke -v
python3 -m pytest test_brief_profiles.py -v   # Phase 2：full byte-identical + lite 精簡斷言
python3 -m pytest test_validate_report_profile_phase3.py -v   # Phase 3：profile Gate + full 等價
REPORT_PROFILE=full SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py   # 與重構前等價檢查
REPORT_PROFILE=lite SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py
REPORT_PROFILE=lite STRICT_INSTITUTIONAL_PHASE_A_GATE=1 python3 -m pytest test_validate_report_profile_phase3.py -v
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
