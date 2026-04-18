# Plan: 日報區塊模組化 — 維護導覽

> **狀態（2026-04）**：**Phase 1–5**（含 **4d**、**5** 〔時事多觀點〕，預設 `BRIEF_CURRENT_AFFAIRS=0`）**已全數落地**。歷史切片、測試與逐日變更以 **[`CHANGELOG.md`](CHANGELOG.md)** 為準，**不要**在本檔重複抄寫全文。權威條目：**2026-04-14**（Phase 4d）、**2026-04-16**（Phase 4c）、**2026-04-26**（Phase 1）、**2026-04-27**（Phase 2–5／4a–4b／Gate Phase 3）。計畫文件與 CHANGELOG 的收斂說明見 **CHANGELOG `## 2026-04-18` → `### Docs`**。

---

## 閱讀地圖

1. 下表 **Phase 與 CHANGELOG 錨點**（狀態一覽）  
2. **產品與交付原則**（過渡期零漂移、完成後組織客製）  
3. **維護紀律**（byte-identical、`REPORT_PROFILE`、YAML 語意）  
4. **長期／非本 plan 預設交付**、**NOT in Scope**、**Verification**、**Critical Files**

---

## Phase 與 CHANGELOG 錨點

| Phase | 狀態 | 關鍵交付 | 變更日誌 |
|:-----:|:----:|----------|----------|
| **1** 模板原子化 | ✅ | `templates/blocks/*.j2`；與 [`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) **byte-identical** | 2026-04-26、27 |
| **2** 版型與組裝器 | ✅ | [`brief_profiles.py`](brief_profiles.py)、`templates/profiles/telegram_{full,lite}.j2`、`REPORT_PROFILE`、`render_telegram_daily_brief(..., profile=)` | 2026-04-27 |
| **3** Gate 與契約 | ✅ | `validate_report(..., profile=)`、profile-aware Phase A/B/C、[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py) | 2026-04-27 |
| **4a** `crypto-only` | ✅ | [`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2) 等 | 2026-04-27 |
| **4b** YAML layout | ✅ | [`brief_profiles_layout.py`](brief_profiles_layout.py)、[`config/brief_layouts/`](config/brief_layouts/)、`BRIEF_LAYOUT_FILE` | 2026-04-27 |
| **4c** BQ `profile` | ✅ | [`bigquery_writer.py`](bigquery_writer.py)、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql) | 2026-04-16 |
| **4d** 1–4 補強 | ✅ | 非法 `REPORT_PROFILE` 啟動檢、文件／一致性 | 2026-04-14 |
| **5** 時事多觀點 | ✅（預設關閉） | [`current_affairs_crew.py`](current_affairs_crew.py)、schemas、`assemble` 注入、strict Gate；LangGraph 路徑同 main 鉤子 | 2026-04-27 |

> 預設 **`REPORT_PROFILE=full`** 與 Phase 0 凍結基線 **byte-identical**；生產行為零漂移。

---

## 背景與意圖（摘要）

**Why：** 單一巨型 `telegram_report.j2` 難維護；需 **named profile** + **有序 block_id** + **profile-aware `validate_report`**，讓組織可差異化版型而不分叉資料管線。

**Intended outcome：** `BLOCK_REGISTRY`／`templates/blocks/*.j2`／`PROFILES`；資料仍由既有 assemble／tools 注入（首階不在區塊內第二套抓數）。

---

## 產品與交付原則

### 過渡期 — 不影響日報產出

1. **`full` 等價**為合併門檻；production 固定或非必要不切離 `full`。  
2. **單一資料管線**：差異落在模板／profile／組裝順序。  
3. 新版型僅 **staging／手動**驗證後再綁 cron。

### 完成後 — 組織級客製

| 機制 | 作用 |
|------|------|
| `REPORT_PROFILE` | 讀本厚度與區塊集合 |
| `BLOCK_REGISTRY` + `templates/blocks/*.j2` | 區塊級責任邊界 |
| 可選 `config/brief_layouts/*.yaml` | **同集合** block **順序**覆寫（`profile_block_ids()`）；預設 **不**驅動 Telegram Jinja 實際 macro 順序，除非 **`BRIEF_DYNAMIC_RENDER=1`** |
| `validate_report(..., profile=)` | 避免 lite 被 full 專用 Gate 誤擋 |
| BQ `profile` | 營運稽核版型使用 |

---

## 維護紀律（必守）

1. **`full` 輸出**與 [`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) **byte-identical**（[`test_telegram_template_modularization.py`](test_telegram_template_modularization.py)，`pytest -m smoke`）。  
2. **非法 `REPORT_PROFILE`**：啟動時 [`main._validate_report_profile_env`](main.py) 應擋。  
3. **`BRIEF_LAYOUT_FILE`**：僅允許內建 profile 之 **同集合重排**；語意見 [`config/brief_layouts/README.md`](config/brief_layouts/README.md)。

---

## 長期／後續產品項（非本 plan 預設交付）

| 項目 | 說明 |
|------|------|
| 時事區塊營運預設開啟 | staging 驗收後將 `BRIEF_CURRENT_AFFAIRS=1` 納入營運決策 |
| 租戶級 layout | 需產品決策 |
| 雙訊息／`DAILY_BRIEF_V2` Phase C | 見 [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) |
| per-user tone、音訊／TTS | 見 NOT in Scope |

---

## Critical Files（速查）

| File | 用途 |
|------|------|
| [`templates/telegram_report.j2`](templates/telegram_report.j2)、[`templates/profiles/telegram_*.j2`](templates/profiles/) | Profile 入口與組裝 |
| [`templates/blocks/*.j2`](templates/blocks/) | Block macro |
| [`brief_profiles.py`](brief_profiles.py)、[`brief_profiles_layout.py`](brief_profiles_layout.py) | Registry、YAML merge |
| [`report_render.py`](report_render.py)、[`report_html_gates.py`](report_html_gates.py) | 渲染與 Gate |
| [`main.py`](main.py)、[`current_affairs_crew.py`](current_affairs_crew.py)、[`schemas.py`](schemas.py) | Phase 5 管線 |
| [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) | 區塊順序與寫作契約 |

---

## Verification

```bash
ruff check .
python3 -m pytest -m smoke -v
python3 -m pytest test_brief_profiles.py -v
python3 -m pytest test_validate_report_profile_phase3.py -v
REPORT_PROFILE=full SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py
REPORT_PROFILE=lite SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 main.py
python3 -m pytest test_critical_paths.py::TestEnvValidation::test_validate_report_profile_env_raises_on_invalid -v
```

---

## NOT in Scope

- Per-user profile／即時 tone（無設定儲存前）
- 每靜態區塊各一專屬 LLM Agent（預設架構）
- Email／web 同套模板（escape 不同）
- run 中切 profile
- 區塊級快取（與 tools cache 分開）
- 超過 **3** 個內建 profile 再擴（需產品決策）
- 真實音訊 podcast 託管／TTS

---

## 延伸閱讀

- PWA／戰情室 **剩餘視覺化 backlog**：[`visualization_plan.md`](visualization_plan.md)
- 決策附錄（Grok、一區塊一 Agent、時事多觀點文字形態）若需完整論述，可查 git 歷史版 `modularization_plan.md` 或對齊 **CHANGELOG 2026-04-27** 正文。

---

## Optional：repo 體積維護（與模組化無硬依賴）

```bash
git rm -r .claude/skills/gstack/
echo '.claude/skills/gstack/' >> .gitignore
```
