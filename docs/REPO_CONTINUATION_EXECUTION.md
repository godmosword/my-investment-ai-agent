# Repo 延續方向執行版（2026 Q2）

本文件將「方向盤點」轉成可執行路線，對齊：

- `TODOS.md`（優先順序與未完成項）
- `docs/ROADMAP_VISION.md`（紅線與 Phase 1–4）
- `docs/TOOLS_MODULARIZATION_PLAN.md`（tools 平台化）

---

## 0) 執行原則（先守紅線再擴功能）

1. 客觀數字一律由工具層與可驗證資料來源注入，禁止 LLM 推導報價。
2. 任一新流程仍需經 `validate_report`；Telegram HTML 白名單不得放寬。
3. 大改採「小切片 + 可回滾」：每個切片都要有 smoke 測試與明確驗收。

---

## 1) Trust/Gate 閉環（短期最高優先）

### 目標

把「可出報」與「可信任」的操作邊界定義清楚，並讓 Gate 失敗可被快速處理。

### 交付物

- 定稿 `docs/CRITICAL_ENV_POLICY.md`，明確區分 local/staging/prod 的 `PIPELINE_STRICT_ENV` 策略。
- 執行 `docs/STAGING_THRESHOLD_EXPERIMENT.md` 的閾值實驗並記錄結果。
- 完成 Gate 失敗的人審流程對齊 `docs/GATE_FAILURE_HINT_WORKFLOW.md`。
- 補齊模板顯示工程債：`templates/telegram_report.j2` 的 trade leg 顯示一致性（含台股顯示規則）。

### 驗收條件

- 至少一輪 staging 實驗有結果檔與決策結論。
- Gate 失敗可定位到「規則、範本、資料缺口」其中之一，且有對應操作建議。

---

## 2) Tools 平台化（中期核心工程）

### 目標

降低 `tools_legacy.py` 維護風險，讓工具可測、可替換、可受控擴充。

### 交付物

- 依 `docs/TOOLS_MODULARIZATION_PLAN.md` 逐步搬移 `tools_legacy.py` 到 `tools/*.py`。
- 共用能力統一到 cache/http 層（`tools_cache_http.py` 與 `tools/` 子模組）。
- 補強 mock fixtures 與 smoke，確保 contributor 不依賴真實 API 也可驗證。
- 受控擴充 OSS Scout 2B（HuggingFace/GraphQL）但保留 PR 人審。

### 驗收條件

- 每次搬移都可在 `pytest -m smoke` 綠燈下落地。
- 新資料來源若未走工具契約，不得進入最終報告主路徑。

---

## 3) Product Shell（方向 1）

### 目標

強化讀者面體驗，同時維持日報主線與商業化能力解耦。

### 交付物

- 對齊 `docs/DASHBOARD_CONTRACT.md`，校準 `dashboard.py` / `api.py` / `data-verification-ui/` 欄位契約。
- 推進 `docs/PWA_WEB_PUSH_NEXT.md` 的持久化方案。
- 商業化能力遵守 `docs/COMMERCE_PLAYBOOK.md`：優先落在 API/PWA 讀取層。

### 驗收條件

- PWA 與 dashboard 看到的一級 KPI 欄位定義一致。
- 商業化實作不改寫 `validate_report` 與報告生成主路徑。

---

## 4) Multi-Agent（Direction 3 試點）

### 目標

在不破壞主 pipeline 的前提下，驗證 company crew 的可行性與成本。

### 交付物

- 以 `crew_company.py` + `company_ops_schemas.py` 做最小可行試點。
- 量測 `CREW_FUTURE_TIMEOUT_SEC`、token 消耗、失敗率，形成基線。

### 驗收條件

- 有可重現的量測紀錄（至少涵蓋成功率、平均耗時、token 區間）。
- 不影響 `main.py` 既有雙線程主流程與 thread safety。

---

## 5) Deploy Cache 優化（快迭代槓桿）

### 目標

縮短 `build-and-deploy` 平均時長，避免大映像在 GHA cache export 卡住。

### 交付物

- 在 `.github/workflows/deploy.yml` 做 cache 策略 A/B（例如 `mode=max` vs `mode=min`）。
- 記錄至少 3 次 deploy 的 build 時間與 cache export 時間。

### 驗收條件

- 中位 deploy 時間相較基線下降，且成功率不下降。
- 無破壞既有 production environment 審批與 Secret Manager 掛載。

---

## 6) 長期 Phase 2–4（決策門檻）

### 目標

把 execution/LangGraph/RAG 規劃成「可決策」而非「立即開工」項目。

### 決策前置

- execution engine：先完成合規與產品定位決議（研究日報 vs 執行系統）。
- LangGraph：先定義與 `crew.py` 的切換邊界與回退策略。
- RAG/語音：先定義資料來源白名單，避免與無幻覺紅線衝突。

### 驗收條件

- 每一條長期路線都有「啟動條件、停止條件、回退策略」。

---

## 建議節奏（30/60/90）

- Day 0–30：完成 Track 1（Trust/Gate）+ Track 5（deploy 快取基線）。
- Day 31–60：推進 Track 2（tools 平台化第一批）+ Track 3（PWA/dashboard 契約）。
- Day 61–90：Track 4 試點量測，並產出 Track 6 的決策文件。

