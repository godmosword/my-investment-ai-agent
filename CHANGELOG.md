# Changelog

本檔案記錄專案重要功能與行為變更。  
**工程待辦與完成度彙總**見 [`TODOS.md`](TODOS.md)；改版時請同步更新該檔對應項目狀態。

## 2026-04-16

### Changed
- **LangGraph `news_scraper_node`**：[`graph/graph_nodes.py`](graph/graph_nodes.py) 對多來源新聞改以 **`ThreadPoolExecutor`** 並行呼叫既有工具，再依原先來源順序合併與 dedupe（上限 6 則），縮短牆鐘時間。
- **`trade_picker`**：`_get_trade_picker_llm` 改為 **`lru_cache(maxsize=1)`** 單例，避免同程序多次 graph invoke 重複建構客戶端。

### Docs
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：補 **`GRAPH_LLM_TRADE_PICKER`**；更新 **`LANGGRAPH_SKIP_FORMATTER_CREW`** 註解（對齊 news／trade 節點組裝）。

### Tests / Tooling
- [`pytest.ini`](pytest.ini)：設定 **`asyncio_default_fixture_loop_scope = function`**，消除 pytest-asyncio 預設 loop scope 棄用警告。

## 2026-04-14

### Changed
- **LangGraph Final_Formatter**：[`graph/graph_nodes.py`](graph/graph_nodes.py) 於 **`LANGGRAPH_SKIP_FORMATTER_CREW=1`** 時改走 **native**（slim 結構化 LLM + 決定性組裝 `CryptoSection`／`AISection`），不再回傳 stub；legacy 路徑將 Bull/Bear/Arbiter 摘要經 **`langgraph_debate_context`** 注入 [`crew.py`](crew.py) Formatter Crew。新增 [`graph/graph_formatter_schemas.py`](graph/graph_formatter_schemas.py)（`CryptoFormatterNarrative`／`AIFormatterNarrative`）；`regime` 可由 `agreed_regime` 或 `regime_scorecard` 字串回退；`score_suffix` 正則支援全形括號。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：`LANGGRAPH_SKIP_FORMATTER_CREW` 註解對齊上述語意與 API 需求。

### Tests
- [`test_graph_crew.py`](test_graph_crew.py)：Formatter mock、native assemble、`run_langgraph_category` 路徑覆蓋。

## 2026-04-15

### Changed
- **Deploy／Cloud Run**：[`deploy.yml`](.github/workflows/deploy.yml) 於 `gcloud run jobs deploy` 加上 **`--update-env-vars=USE_LANGGRAPH_ENGINE`**，值取自 GitHub **Environments → production** 變數 `USE_LANGGRAPH_ENGINE`（未設則 `0`）。[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) 補操作說明。

## 2026-04-13

### Changed
- [`crew.py`](crew.py)：新增 **【華爾街級財報分析】** 寫作規則（結論→工具數字證據→倍數／指引含義；禁臆造共識 EPS／beat-miss；主編共識與區塊④須回溯季報讀值），並注入 `_CREW_RULE_BLOCK` 與 Crypto／AI **結構化最終主編** prompt。
- [`earnings_focus.py`](earnings_focus.py)：【財報聚焦日】exclusion 對齊同一敘事骨架。
- [`crew.py`](crew.py)、[`earnings_focus.py`](earnings_focus.py)：**beat／miss** 僅允許於新聞 **title/summary** 已含「共識／預期／Street…」等對照語時使用；**FY／前瞻指引**僅能複述同則新聞字面，否則僅能寫「待法說／IR」。

## 2026-04-12

### Changed
- [`earnings_watchlist.py`](earnings_watchlist.py)：`MEGA_CAP_TECH_EARNINGS_TICKERS` 新增 **AI 伺服器／ODM**（`SMCI`、`DELL`、`HPE`）、**資料中心網路**（`ANET`、`CSCO`）、**矽光子／光通訊供應鏈**（`LITE`、`COHR`、`FN`）。
- [`README.md`](README.md)：watchlist 列表同步。

## 2026-04-11

### Changed
- [`earnings_watchlist.py`](earnings_watchlist.py)：擴充 **AI／雲端／半導體** 財報 watchlist（`INTC`、`MRVL`、`QCOM`、`MU`、`ORCL`、`CRM`、`NOW`、`SNOW`、`PLTR`、`CRWD`、`NET` 等；來源為公開市場常見分類（非排名、非即時選股）。
- [`earnings_focus.py`](earnings_focus.py)：**週五**錨定日亦注入 **【下週財報預告】**（與週六／日相同，指向下一曆週 Mon–Sun）。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README.md`](README.md)：同步「週五亦預告」與擴充後代號列表。

### Tests
- [`test_earnings_watchlist.py`](test_earnings_watchlist.py)、[`test_earnings_focus.py`](test_earnings_focus.py)：週五範圍與預告文案。

## 2026-04-10

### Added
- [`earnings_watchlist.py`](earnings_watchlist.py)：共用 **mega-cap／AI 財報 watchlist**、`pipeline_anchor_date`、錨定**曆週**（Mon–Sun）掃描、週末→**下週一～日**範圍輔助。

### Changed
- [`tools_legacy.py`](tools_legacy.py) `macro_context_tool`：本週財報改為 **錨定週**（`PIPELINE_REPORT_DATE` 或 UTC 當日所在週）內之 watchlist 排程；並附 **盤前／盤後**說明行（yfinance 多僅公告日）。
- [`earnings_focus.py`](earnings_focus.py)：**週六／週日錨定日**一律注入 **【下週財報預告】**（下一完整曆週）；【財報聚焦日】補 **盤前／盤後**與「已發／待發」規則。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README.md`](README.md)、[`CLAUDE.md`](CLAUDE.md)：文件補齊 watchlist 列表與週末行為。

### Tests
- [`test_earnings_watchlist.py`](test_earnings_watchlist.py)（smoke）：曆週與週末 Mon–Sun 範圍。
- [`test_earnings_focus.py`](test_earnings_focus.py)：週末預告、盤前盤後字樣。

## 2026-04-09

### Added
- **財報聚焦日（可選）**：[`earnings_focus.py`](earnings_focus.py) 於 **`EARNINGS_FOCUS_MODE=1`** 或 **`auto`** 時，依 yfinance 日曆偵測錨定日是否為 watchlist（NVDA、MSFT、AAPL 等）**財報公告日**，並在 [`main.py`](main.py) 注入 **【財報聚焦日】** exclusion，要求 AI 段對命中標的呼叫 **`financial_datasets_tool('TICKER:quarterly')`**、新聞與交易須錨定工具讀值。見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **LangGraph 深度查證工具橋接**：[`graph/graph_tools.py`](graph/graph_tools.py) 以 `langchain_core.tools.tool` 包裝 `coinglass_data_tool`、`financial_datasets_tool`、`newsapi_tool`，匯出 `RESEARCH_TOOLS` 供 `bind_tools` 使用。

### Changed
- [`graph/graph_nodes.py`](graph/graph_nodes.py)：`deep_research_node` 將查證結果寫入 `raw_data['deep_dive_round_N']`；可選 **`GRAPH_DEEP_RESEARCH_TOOL_LLM=1`**（且 `GRAPH_ENABLE_TOOL_CALLS=1`）時以 `bind_tools` 多輪執行真實工具並附 `ToolMessage`；預設仍走決定性 probe（CI／無金鑰安全）。Arbiter（LLM）規則 1 改為要求「非常明確的 API 查詢關鍵字或指令」。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：補 `GRAPH_DEEP_RESEARCH_TOOL_LLM`、`EARNINGS_FOCUS_MODE` 註解。
- [`report_render.py`](report_render.py)：`assemble_daily_brief_report` 新增 **`_postprocess_brief_data_hygiene`**：中和未驗證之 **BTC 減半／840,000** 日曆列；**三情境**去重行首 `·`；宏觀寫 **Contango** 時將敘事失效之 **Backwardation** 改寫為現貨 VIX 門檻；**加密儀表板** FinancialDatasets `N/A` 時自 **AI 儀表板**補 NVDA/MSFT 錨點；剪除新聞 **investment_takeaway** 與日曆名目金額無關硬湊；**crypto_cycle**／**exec_summary** 弱化減半與無來源「歷史顯示」句。
- [`schemas.py`](schemas.py)：`ChatterItem` 在已有可信度標記但缺 **主流媒體二次驗證** 時自動補「否」。
- [`crew.py`](crew.py)：`exec_summary` 禁無來源統計口號；Phase A/B/C 規則補 **減半禁寫**、**VIX 期限結構一致**、**scenario_probability_notes** 勿重複行首 `·`、日曆金額勿剪貼進無關新聞解讀。

### Tests
- [`test_graph_crew.py`](test_graph_crew.py)：深度迴圈路徑斷言 `raw_data` 含 `deep_dive_round_1`。
- [`test_report_render.py`](test_report_render.py)：組裝衛生（減半日曆、三情境 bullet、VIX 同步、FD 補齊、新聞剪貼、週期／執行摘要 scrub、Chatter MSM 補齊）。
- [`test_earnings_focus.py`](test_earnings_focus.py)（smoke）：exclusion 區塊與 `maybe_prepend` 行為。

### Docs
- [`README.md`](README.md)：重寫為精簡導覽（情境表、Mermaid、`graph/` 與 **`graph_tools`／`RESEARCH_TOOLS`**、`GRAPH_DEEP_RESEARCH_TOOL_LLM` 對照表、驗證／CI 索引）；**預設分支 `main`**、直推觸發 deploy 見 [`AGENTS.md`](AGENTS.md)；環境摘錄補 **`EARNINGS_FOCUS_MODE`**。
- [`CLAUDE.md`](CLAUDE.md)：模組表補 [`earnings_focus.py`](earnings_focus.py)。
- [`TODOS.md`](TODOS.md)：檔首同步 **2026-04-09**；補 **LangGraph 路徑**未勾選項；**演進藍圖 Phase 3** 標註骨架與 deep research 工具橋接已部分落地；Pri 表與模板工程債敘述收斂。

## 2026-04-08

### Added
- **華爾街級 Phase C**：`CryptoSection` 新增 `crypto_cycle_valuation_notes`、`equity_valuation_framing`、`event_calendar_lines`；`ExecutableTradeLeg.liquidity_execution_note`；模板增【加密週期與估值錨】【美股估值與修正框架】【近端事件日曆】及交易卡「流動性／執行」。`STRICT_INSTITUTIONAL_PHASE_C_GATE=1` 啟用 HTML／結構化 Gate。`crew.py` 新增 `_INSTITUTIONAL_PHASE_C_RULE`。
- **華爾街級 Phase B**：`CryptoSection` 新增 `portfolio_framing_summary`、`scenario_probability_notes`（三行樂觀/基準/悲觀＋機率合計 100%）；`NewsItem.pricing_note`（「未定價／增量資訊」「大致已定價」「已高度反應」）；模板於命題區後渲染【組合與曝險框架】【三情境機率】，新聞列印 `<i>市場定價</i>：<code>…</code>`。`STRICT_INSTITUTIONAL_PHASE_B_GATE=1` 時 HTML 與結構化雙檢（`report_html_gates._institutional_phase_b_html_ok`、`schemas._institutional_phase_b_structured_issues`）。`crew.py` 新增 `_INSTITUTIONAL_PHASE_B_RULE`。
- **新聞新鮮度預設視窗**：`NEWS_FRESHNESS_WINDOW_HOURS` 預設由 48 改 **36**（與 `_DATA_RULES` 一致）；`ENV_TEMPLATE.txt` 註解同步。
- **華爾街級 Phase A（機構讀者）**：`CryptoSection` 新增 `investment_thesis_one_liner`、`thesis_supporting_points`（3）、`thesis_contrary_points`（3）、`key_assumptions_lines`（2–4）、`narrative_invalidation_summary`；`DailyBriefReport.institutional_disclaimer_html` 於 `assemble_daily_brief_report` 注入固定 Telegram 白名單免責（`report_render._INSTITUTIONAL_DISCLAIMER_HTML`）；`templates/telegram_report.j2` 於標題後渲染免責與命題區塊。
- **可選 Gate**：`STRICT_INSTITUTIONAL_PHASE_A_GATE=1` 時 `validate_report` 檢查 HTML 區塊；同開關下 `DailyBriefReport` 結構化驗證要求上述欄位（`schemas._institutional_phase_a_structured_issues`）。見 `ENV_TEMPLATE.txt`。
- **Crew**：`crew.py` 新增 `_INSTITUTIONAL_PHASE_A_RULE` 並掛入加密結構化最終提示。
- **切片 4 量測基線**：[`main.py`](main.py) 新增可選 `SHADOW_BENCHMARK_LOG=1` 與 `SHADOW_BENCHMARK_PATH`，會將 `crewai_dual_crew`／`langgraph_dual_crew`／`company_growth_context` 的耗時與新聞量寫入 JSONL，供 company crew 與 LangGraph shadow 成本評估（不影響主流程）。

### Changed
- [`README.md`](README.md)：全文重寫與重排（專案紅線、情境表、**雙軌研究引擎** Mermaid、**LangGraph**／`graph/`、`USE_LANGGRAPH_ENGINE`、機構 Phase A/B/C 可選 Gate 與 `ENV_TEMPLATE` 索引）；精簡重複段落並對齊現行模組、CI 與 PWA 說明。
- [`report_render.py`](report_render.py)：`assemble_daily_brief_report` 組裝時將 **QSREC** 每筆可選 `regime` **強制對齊** `crypto.market.regime`（消除與【今日市場模式】主判定不一致的 warning）；並在主判定為 `neutral`／`risk_on` 時，修正 `us_equity_allocation_note` 內誤寫的 `（risk_off）` 括號為「對齊主判定：…」。
- [`crew.py`](crew.py)：收斂 **AI 儀表板**（FinancialDatasets 以 NVDA+MSFT 為 anchor、其餘檔位上限行數；開源動能至多 2 行）；**AI 產業新聞**禁以加密／VIX 作主線、新聞新鮮度改 **36h**；QSREC 提示 **省略 `regime` 欄**（由管線對齊）。
- **Gate digest 人審稿**：[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py) 新增 `gate_code` 分布摘要，並支援 `GATE_FAILURE_DIGEST_OUT` 直接輸出 Markdown 檔；保持「僅摘要、不自動改 prompt」邊界。
- **Mock smoke 進 CI**：[`ci.yml`](.github/workflows/ci.yml) 在 quick tier 新增 `./scripts/run_mock_smoke.sh`，確保 `MOCK_APIS=1` 路徑在 PR/可呼叫 CI 皆有驗證。

### Tests
- [`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)：新增 `assemble` 對 QSREC regime 與美股部位框之 smoke 覆蓋。
- [`test_validate_report.py`](test_validate_report.py)：`TestStrictInstitutionalPhaseAHtmlGate`、`TestStrictInstitutionalPhaseBHtmlGate`、`TestStrictInstitutionalPhaseBStructuredGate`、`TestStrictInstitutionalPhaseCHtmlGate`、`TestStrictInstitutionalPhaseCStructuredGate`；`_make_report` 可選 Phase B/C；`_make_minimal_structured_report_dbr` 含 `pricing_note` 與可選 Phase C 欄位。
- [`test_smoke_pipeline.py`](test_smoke_pipeline.py)、[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)：最小報告字串補 Phase A+B+C、市場定價行與流動性註記；新聞括號時間改動態（`STRICT_NEWS_FRESHNESS_GATE=1` 時 smoke 仍過）。
- [`test_report_render.py`](test_report_render.py)、[`test_news_freshness.py`](test_news_freshness.py)：樣本新聞 `pricing_note`；新鮮度測試視窗 36h；render 測試含 Phase C 欄位與 `liquidity_execution_note`。
- [`conftest.py`](conftest.py)：BigQuery stub 補 `QueryJobConfig`（pick rotation／參數化查詢路徑不再因 stub 缺類別失敗）。

## 2026-04-07

### Added
- [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md)：將「依目前 repo 架構可延續方向」落成執行版路線圖（Trust/Gate、tools 平台化、Product Shell、Multi-Agent、deploy cache、Phase 2–4 決策門檻），含 30/60/90 節奏與各 track 驗收條件。

### Changed
- [`TODOS.md`](TODOS.md)：檔首新增「執行版路線圖」連結，便於維護者從彙總待辦直接跳轉到可執行規劃。
- [`README.md`](README.md)：索引與「下一步讀哪裡」補上 [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) 入口，讓新進開發者可直接看到可執行路線。
- **戰報 Gate／敘事一致性**：[`report_html_gates.py`](report_html_gates.py) 主判定為 `neutral`／`risk_on` 時，**美股部位框**行內括號誤標 `（risk_off）` 列入 `_risk_off_narrative_violations`；`has_mixed_regime` 僅看正文 **mode／budget** 標籤（不含僅 QSREC JSON 分歧）；動態選幣理由強關鍵詞補 **期貨／衍生品／CME／恐慌／貪婪／恐懼貪婪**；QSREC 單筆 `regime` 與【今日市場模式】主判定不一致時列入 `_qsrec_consistency_issues`。
- **Crew 提示詞對齊**：[`crew.py`](crew.py) 美股部位框括號須與主判定一致；執行摘要避免在 `neutral`／`risk_on` 使用僅適用 `risk_off` 的語氣；Gate 預檢選幣理由關鍵詞池與 Gate 一致。
- **Phase 3 LangGraph 骨架落地**：新增 [`graph/graph_state.py`](graph/graph_state.py)、[`graph/graph_nodes.py`](graph/graph_nodes.py)、[`graph/graph_crew.py`](graph/graph_crew.py) 與 [`graph/__init__.py`](graph/__init__.py)，實作 StateGraph（Gather → Bull/Bear 並行 → Arbiter 條件路由 → Deep Research 迴圈 → Final Formatter）；[`main.py`](main.py) 新增 `USE_LANGGRAPH_ENGINE` 分支（預設關閉，與既有 CrewAI 並存）；[`config.py`](config.py)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`requirements*.txt`](requirements.txt) 同步新增切換與相依設定。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：`TestValidateReport` 新增／收斂 **risk_off 敘事**、**CME／期貨選幣理由**、**QSREC regime 與主判定**、**mixed regime 忽略僅 QSREC 分歧** 等案例。
- [`test_graph_crew.py`](test_graph_crew.py)：新增 `raw_data` reducer 不突變合併、LangGraph `compile()/invoke()` smoke、`research_depth` 迴圈上限守衛測試。

## 2026-04-04

### Added
- **可選嚴格核對**：[`report_html_gates.py`](report_html_gates.py) `STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE=1` 時，加密／AI 每則 `<i>投資解讀</i>` 之數字錨點須與同段 `<b>區塊①</b>` 儀表板內 `<code>` 讀值可對照；**觀望模式**略過；該 issue 為 **blocking**。見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **BTC 均線儀表列**：[`report_render.py`](report_render.py) `assemble_daily_brief_report` 在儀表板尚未含 MA20/MA50 列時，以 yfinance 日線注入 **`BTC MA20（日線）`／`BTC MA50（日線）`**（`SKIP_BTC_MA_DASHBOARD_INJECT=1` 或 `MOCK_APIS=1` 時略過）。
- **呢喃 MSM Gate（可選）**：`STRICT_CHATTER_MSM_VERIFY_GATE=1` 時，區塊③含「可信度」之 `·` 條目須含「主流媒體二次驗證」；blocking。
- **演進計畫落地（信任／觀測／分叉）**：[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) 定稿、[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) 補實驗表；[`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) 在 `ADAPTIVE_GATE_THRESHOLDS=1` 時可自 BigQuery `gate_failure_log` 讀取 rotation 相關失敗占比並 **bump** `PICK_ROTATION_OVERRIDE_MIN_GAP`（`ADAPTIVE_GATE_BQ_READ=0` 關閉 BQ 讀取）；[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)；[`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)＋[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)；[`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)；[`report_render.py`](report_render.py) 備援觸發時可寫 scratchpad `equity_price_backfill`（`EQUITY_BACKFILL_SCRATCHPAD_LOG`）；[`schemas.py`](schemas.py) 可選 `asset_market`、`AISection` 觀望 vs EQUITY QSREC **warning**；[`docs/PWA_WEB_PUSH_NEXT.md`](docs/PWA_WEB_PUSH_NEXT.md)、[`docs/TW_EQUITY_DISPLAY.md`](docs/TW_EQUITY_DISPLAY.md)。`ENV_TEMPLATE.txt` 補自適應與 scratchpad 變數。

### Fixed
- **投資解讀量化 Gate 誤判**：[`validation_rules.py`](validation_rules.py) 之 `NUMERIC_INVESTMENT_*` 改為 `投資解讀\s*[：:]`，對齊 [`templates/telegram_report.j2`](templates/telegram_report.j2) 的 `<i>投資解讀</i>：`（strip HTML 後標籤與冒號間有空格時仍視為有效錨點）。

### Changed
- **待辦決策文件**（[`TODOS.md`](TODOS.md)）：新增「未完成項四維評分與新建議（2026-04）」— Pri 1–9 與波次／Phase 濃縮評分表、建議實作順序、七條新建議 backlog（Gate 內部儀表、結構化預檢 dry-run、備援可觀測性、Prompt 登記簿、`asset_market`、mock-smoke 腳本、觀望 vs QSREC 一致性）。[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) 檔首補對照連結。
- [`crew.py`](crew.py) `_NEWS_FMT`／`_CHATTER_FMT`／`_EXEC_SUMMARY_RULE`／`_HEDGE_FUND_BRIEF_RULE`／`_DASHBOARD_FMT`：AI 新聞投資解讀禁跨段主錨點（BTC/VIX/SPY 等）；加密新聞 MA 須對儀表 MA 列；呢喃禁 `MSM` 英文簡寫；執行摘要去重；交易失效條件須對已列讀數。
- [`templates/telegram_report.j2`](templates/telegram_report.j2)：`position_pct`、`trigger` 顯示前 **strip `$`**（Pri 8）。
- [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)：補 digest script／儀表連結與 `PROMPT_CHANGELOG` 登記說明。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：`TestStrictInvestmentDashboardNumericGate`、`TestChatterMsmVerifyGate`；`TestInvestmentNumericAndUnactionableTrade` 補 `<i>投資解讀</i>：` 間距仍過量化 Gate。
- [`test_report_render.py`](test_report_render.py)：`test_ensure_btc_ma_dashboard_rows_inserts_after_btc_spot`。
- [`test_adaptive_gate_thresholds.py`](test_adaptive_gate_thresholds.py)：BQ bump／ceiling；預設 `ADAPTIVE_GATE_BQ_READ=0` 之 smoke。
- [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)：觀望 vs EQUITY QSREC warning。
- [`test_validate_report_dry_run_smoke.py`](test_validate_report_dry_run_smoke.py)：Gate 骨架與 `validate_report` 對齊。

## 2026-04-03

### Added
- **美股 trade_legs 價位備援**（[`report_render.py`](report_render.py)）：`assemble_daily_brief_report` 在 `MOCK_APIS` 未開啟且未設 `SKIP_EQUITY_YF_BACKFILL=1` 時，以 [`tracker.py`](tracker.py) `yfinance` 批次補 **現價／進場**；若 **目標／停損** 皆缺且 R:R、最大回撤可解析，依風險比例機械推算（LONG／SHORT 對稱）。例外時記錄 warning 並略過備援。
- **加密儀表板爆倉缺數提示**：全文儀表板未出現「爆倉」或「清算」時自動追加一行 ⬜ **備註**（引導以費率／OI／多空比代理觀察）。

### Fixed
- **validate_report**：投資解讀「當日量化」改為先 **strip HTML** 再比對（[`validation_rules.py`](validation_rules.py) `plain_text_for_investment_numeric_gate`）；數字樣式允許 **負號**（如資金費率 -0.0008%）。**不可執行交易** Regex 涵蓋 **`現價：<code>$N/A</code>`**、全形 `｜` 分隔（[`validation_rules.py`](validation_rules.py) `UNACTIONABLE_TRADE_RE`）；[`report_postprocess_legacy.py`](report_postprocess_legacy.py) 移除不可執行區塊時對齊同一規則。
- **結構化 QSREC／STRICT_CONSISTENCY**：[`schemas.py`](schemas.py) `TradeRecommendation` 於 `score_gap` 缺漏且已有 `selection_score` 與 `alt_candidate_score` 時，在模型解析前自動補 **score_gap = selection_score − alt_candidate_score**（與 crew 分差契約一致，非捏造），避免 `DailyBriefReport` 業務驗證僅因漏填 gap 失敗而觸發 **GATE_EXECUTION_FAILED**。

### Changed
- **讀者面向日報**：[`validation_rules.py`](validation_rules.py) 同標延續前綴改為 **「連日維持與昨日相同建議標的」**（仍命中 `_REPEAT_PICK_REASON_RE`），移除 **pipeline／BQ** 內部字樣；[`report_render.py`](report_render.py) 組裝時對空白 **`trade_legs.position_pct`** 依 regime＋星級補齊（[`tracker.py`](tracker.py) `default_position_pct_for_leg`）；**美股兩檔及以上**再依單筆上限壓縮並按 **合計上限**（neutral 10%／risk_on 15%／risk_off 4%，見 `equity_combined_cap_percent`）等比縮放；[`schemas.py`](schemas.py) 呢喃 **（未確認）** 且 **可信度：A** 時自動降 **B**；[`crew.py`](crew.py) **【讀者面一致】**、呢喃 A 級、新聞跨域；`_NEWS_FMT` 補跨板塊一句；**投資解讀 Gate／美股交易卡價位／24h 爆倉儀表板** 規則補強（與上述備援與 Regex 對齊）。
- **Telegram 模板質感**（[`templates/telegram_report.j2`](templates/telegram_report.j2)）：標題後統一分隔線；執行摘要標題顯式 **【執行摘要】**（對齊 `STRICT_EXEC_SUMMARY_HTML_GATE`）；**【今日市場模式】** regime 以 `<code>` 凸顯；區塊編號粗體、主敘事／新聞「投資解讀／主編共識」以 `<i>` 標示；加密段與 **🤖 AI 市場** 之間補 **────────────**（利於 `_crypto_report_prefix` 邊界）；多腿交易之間 **────────** 換氣。
- **讀者面語氣／分域／選股廣度**（[`crew.py`](crew.py)）：執行摘要補「語氣與節奏」「分域敘事」（禁止無因果混寫加密與美股）；避險基金規則補「精緻度」；研究員候選多樣性補產業／市值廣度；AI 區塊④動態選股補 (d) 兩檔廣度。
- **OSS Scout → TODOS**：[`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) `_build_todos_block` 改為**連結＋摘要表＋短勾選**（不再嵌入 `fit_rationale` 長標籤）；[`templates/oss_weekly_plan.md.j2`](templates/oss_weekly_plan.md.j2) 底部新增 **維護者勾選追蹤**；[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md) 與 [`TODOS.md`](TODOS.md) 靜態說明對齊；[`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md) 補同區塊（與下輪管線輸出一致）。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：投資解讀 HTML 包裝＋負數費率仍過量化 Gate；`現價：<code>$N/A</code>` 觸發不可執行交易擋單。
- [`test_report_render.py`](test_report_render.py)：爆倉備註追加、美股 N/A 價位 assemble 備援與目標／停損合成。
- [`test_report_render_boundaries.py`](test_report_render_boundaries.py)：`position_pct` 解析／補填、`tracker` regime 上限與星級 clamp、美股多腿合計縮放（neutral／risk_on／risk_off）、非法百分比與 `ChatterItem` 可信度邊界。
- [`test_report_render.py`](test_report_render.py)：呢喃 A→B、`assemble` 補 **position_pct**、美股兩檔合計縮放與單筆 clamp；[`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)：`normalize_leading_repeat_pick_phrase` 前綴字串。
- [`test_oss_weekly.py`](test_oss_weekly.py)：`test_build_todos_block_compact_table_and_short_checkboxes`。
- [`test_trade_recommendation_schema.py`](test_trade_recommendation_schema.py)：`test_score_gap_derived_when_omitted_but_scores_present`。

## 2026-04-02

### Added
- **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)**：`workflow_dispatch` 手動觸發（`test_tier` quick／full）；`callable` job 以 `CI_TEST_TIER` 統一讀取 dispatch 與 `workflow_call` 輸入。

### Fixed
- **CI smoke**：將 [`tests/fixtures/mock_data/market.json`](tests/fixtures/mock_data/market.json) 納入版控（先前 CHANGELOG 已列但檔案未提交），修復 `test_market_fixture_loads_when_mock_on`。

### Maintenance
- [`tools/__init__.py`](tools/__init__.py)：`vars(tools_legacy)` 鏡射（取代 `dir()`）；[`api_schema.py`](api_schema.py)、[`validation_rules.py`](validation_rules.py) 註解對齊 `tools_legacy`／`tools`。
- [`TODOS.md`](TODOS.md)：檔首同步 **2026-04-02**；修訂紀錄合併 **2026-03-29** 雙條；補 OSS 自動區塊勿手改提示。

## 2026-03-29

### Changed
- **Tools 套件化 Phase 1（Office Hours Alt B）**：根目錄 monolith 更名為 [`tools_legacy.py`](tools_legacy.py)；新增 [`tools/`](tools/) 套件（[`tools/base.py`](tools/base.py) `MOCK_APIS`／`load_mock_json`、[`tools/market.py`](tools/market.py) `market_fixture_dict`；[`tools/__init__.py`](tools/__init__.py) 自 `tools_legacy` re-export 維持 `import tools` 相容）。說明與分階見 [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md)；[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`CLAUDE.md`](CLAUDE.md)、[`README.md`](README.md) 已對齊。
- **Hugging Face／`ai_momentum_tool`**（[`tools_legacy.py`](tools_legacy.py)）：`_hf_fetch_models(..., prefer_downloads=...)` 預設 **trendingScore → likes → downloads**（弱化下載榜主導），`prefer_downloads=True` 時下載優先；`ai_momentum_tool` 依 `metric` 是否含 `download` 選擇排序；快取鍵區分分支；HF／OpenRouter 標題補「敘事參考／非股價」避免誤讀為股價。
- **FinancialDatasets 儀表指引**：[`tools_legacy.py`](tools_legacy.py) `_fd_summarize_ticker` 要求 watchlist 每檔 **至少三行** MetricLine（營收、同比%、FCF 等），避免基本面濃縮成單行。
- **Crew AI 區塊①**（[`crew.py`](crew.py)）：研究員掛載 **`ai_sector_market_tool`**；`_TOOL_TRUTH_RULE`／`_NEWS_FMT`／`_DASHBOARD_FMT`／`_AI_LAYOUT_RULE`／`build_ai_structured_final_prompt` 與並行任務「必呼叫」對齊建議順序：**yfinance 族群（SMH／SOXX／NVDA／MSFT／GOOGL／SPY）→ FinancialDatasets（每檔≥3 行）→ ai_momentum**。

### Added
- **AI／半導體族群市場工具**：[`tools_legacy.py`](tools_legacy.py) `ai_sector_market_tool`（yfinance 日線批次；上列一籃標的之收盤與 1D／約 5 交易日報酬；`_get_cache`／`_set_cache`、經 [`tools/__init__.py`](tools/__init__.py) re-export）。
- [`tests/fixtures/mock_data/market.json`](tests/fixtures/mock_data/market.json) — mock 市場片段（`MOCK_APIS=1` 時由 `market_fixture_dict` 載入）。

### Tests
- [`test_ai_sector_market_tool.py`](test_ai_sector_market_tool.py)：`ai_sector_market` yfinance 輸出格式；`_hf_fetch_models` 首輪 `sort`（`conftest` yfinance stub 下以 `patch.object(..., create=True)` 掛 `download`）。
- [`test_tools_package_phase1.py`](test_tools_package_phase1.py)（`@pytest.mark.smoke`）。

### Docs / env
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) — `MOCK_APIS` 專節。

## 2026-04-01

### Fixed
- **本日選擇理由雙抬頭**：LLM 若以「重複選用理由：／重複選股理由：／重複持有理由：」開頭，`assemble_daily_brief_report` 會依與昨日 BQ QSREC 是否相同，改寫為 **「連日維持（同昨日 BQ QSREC）；…」** 或僅剥除冗餘前綴（[`validation_rules.py`](validation_rules.py) `normalize_leading_repeat_pick_phrase`、[`report_render.py`](report_render.py) `_normalize_pick_reason_repeat_headers`）。
- **呢喃可信度補填**：[`schemas.py`](schemas.py) `ChatterItem` 與 [`crew.py`](crew.py) `_ensure_chatter_credibility` 改補 **「｜可信度：…｜主流媒體二次驗證：否」**，不再向讀者顯示「（自動補填）」。

### Tests
- [`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)、[`test_report_render.py`](test_report_render.py)：上述行為之單元／assemble 迴歸。

### Maintenance
- **[`TODOS.md`](TODOS.md)**：已落地與檔首同步狀態補 **2026-04-01** 條目。
- **OSS Scout（2026-04-01）**：`OSS_SCOUT_AUTO_*` 候選表更新；研究稿 [`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md)。

## 2026-03-31

### Changed
- **近 30 天績效週報**（[`tracker.py`](tracker.py) `generate_performance_summary`）：附 **指標說明**／**回撤說明**（加權平均、Expectancy、PF、複利淨值 Max DD 與單筆最差之區別）；**Regime 分層**對 `unknown` 與少於 10 筆分組加註樣本解讀，並附一句解讀建議。
- **同標延續補註**（[`report_render.py`](report_render.py)）：自動前綴改為 **「連日維持（同昨日 BQ QSREC）…」**，避免 Telegram 模板「本日選擇理由：」與「重複選用理由：」雙重抬頭；仍符合 [`report_html_gates.py`](report_html_gates.py) `_REPEAT_PICK_REASON_RE`。
- **Crew 寫作規則**（[`crew.py`](crew.py)）：儀表板規格補 **NVT 與 RSI 並存時**之尺度區分；呢喃格式統一 **（未確認）｜來源｜可信度｜二次驗證** 欄位順序；`_DATA_RULES`／`_TOOL_TRUTH_RULE`／`_QUOTE_RULE` 三合一注入改為常數 `_CREW_RULE_BLOCK`（語意不變）。
- **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)**：預設**略過** job 內「Free disk space on runner」（節省約 1–3 分鐘；映像 build 若因 runner 磁碟不足失敗，可暫時還原該步驟）。

### Fixed
- **結構化日報驗證**：`crypto.risk_budget_summary` 若僅中文、未含 `risk_on`／`risk_off`／`neutral` 等 canonical token，[`report_render.py`](report_render.py) 於 `_coerce_sections_for_gate` 依 `market.regime` 自動前綴補齊，避免 `DailyBriefReport` 拋「加密今日風險預算未包含主 regime token」；[`validation_rules.py`](validation_rules.py) 新增 `ensure_crypto_risk_budget_regime_token`；[`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)／[`test_report_render.py`](test_report_render.py) 補測。

### Maintenance
- **[`TODOS.md`](TODOS.md)**：移除已完成 `[x]` 主列表（細節改以本檔 2026-03-28～31 與「已落地（備查）」為準）；新增 **OSS Scout 週報** `<!-- OSS_SCOUT_AUTO_BEGIN -->`／`<!-- OSS_SCOUT_AUTO_END -->`，與 [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 合併邏輯對齊。

### Docs
- **LLM 成本／延遲（營運槓桿）**：[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 新增專節；[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) 對照說明（關閉 editor／judge、`PIPELINE_SKIP_SENTIMENT_SCORE`、`MODEL_*` 降階等）；Runbook **Deploy 併發**敘述與 [`deploy.yml`](.github/workflows/deploy.yml) `cancel-in-progress: true` 對齊。

## 2026-03-30

### Changed
- **日報品質（無幻覺管線）**：[`report_render.py`](report_render.py) 在與昨日 BQ QSREC 標的相同且允許覆核時，若理由缺輪動認可片語則自動前綴補註（`AUTO_REPEAT_PICK_DISCLAIMER`，預設開；見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；初版用語為「重複選用理由：…」，**2026-03-31** 改為「連日維持…」以降低與模板「本日選擇理由：」重複感（見該日 **Changed**）。另：[`tracker.py`](tracker.py) 上期追蹤略過明顯占位進場價／合理區間外；[`tools_legacy.py`](tools_legacy.py) 資金費率絕對值小於 0.01% 時顯示六位小數並標「近零」；[`crew.py`](crew.py)／[`templates/telegram_report.j2`](templates/telegram_report.j2) 對齊執行摘要跨資產框定、減少與儀表板數字重複、區塊②b 改「主題式觀點摘要」敘述。

### Fixed
- **Deploy 觸發 CI 全跳過**：[`.github/workflows/ci.yml`](.github/workflows/ci.yml) 可重用流程內 `github.event_name` 繼承呼叫端（如 `push`）而非 `workflow_call`；`callable` job 改為 `if: github.event_name != 'pull_request'`，使 [`deploy.yml`](.github/workflows/deploy.yml)／[`nightly-ci.yml`](.github/workflows/nightly-ci.yml) 的 `uses:` 會實際執行 lint／pytest。

### Security
- **Git 歷史淨化**：已以 `git filter-repo` 自全部本地分支之歷史移除 `.env.example`，再提交僅含占位符之範本；`main` 與既有本地分支已 **force-push** 至 `origin`。**所有協作者須刪除舊 clone 並重新 clone**（舊 commit SHA 已全部作廢）。建議在 GitHub 啟用 Secret scanning／Push protection。

### Added
- **可選研究工具註記**：[last30days-skill](https://github.com/mvanhorn/last30days-skill) 與日報管線信任邊界、pilot 快照、併入層級 A+B 預設與路徑 C 之 ADR 前置條件 — [`docs/research/LAST30DAYS_SKILL.md`](docs/research/LAST30DAYS_SKILL.md)、[`docs/research/README.md`](docs/research/README.md)；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引與 §9 連結。
- **CI 輕量依賴**：[`requirements-ci.txt`](requirements-ci.txt) — Actions 上 `ruff`／`pytest` 無需安裝 CrewAI／Streamlit／sentence-transformers 等（與 [`conftest.py`](conftest.py) stub 對齊；smoke + full 338 項已驗證）。
- **Nightly 全測**：[`.github/workflows/nightly-ci.yml`](.github/workflows/nightly-ci.yml) — 每日 02:00 UTC（可 `workflow_dispatch`）呼叫 `ci.yml` 且 `test_tier: full`。

### Changed
- **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)**：`pull_request` 略過僅 `docs/**`、`data-verification-ui/**`；`workflow_call` 新增輸入 `test_tier`（`quick`／`full`）；預設 `pip install -r requirements-ci.txt`；PR smoke 不再跑大型釋放磁碟步驟。
- **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)**：`test` job 以 `test_tier: quick` 呼叫 CI；`concurrency.cancel-in-progress: true`；Docker 改 `docker/build-push-action` + GHA cache；`paths` 納入 `requirements-ci.txt`。
- **[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)**：cron 改為每月 **1 與 15 日** 06:00 UTC（較原每週一省分鐘）。
- **[`README.md`](README.md)**、[`AGENTS.md`](AGENTS.md)、[`CLAUDE.md`](CLAUDE.md)：同步 CI／nightly／`requirements-ci.txt` 說明。

## 2026-03-29

### Added
- **邊界條件測試**：[`docs/BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md)；pytest markers `boundary`／`slow`（[`pytest.ini`](pytest.ini)）；[`test_tools_http_contract.py`](test_tools_http_contract.py)、[`test_report_html_gates_boundaries.py`](test_report_html_gates_boundaries.py)、[`test_main_pipeline_boundaries.py`](test_main_pipeline_boundaries.py)、[`test_boundary_hypothesis.py`](test_boundary_hypothesis.py)（Hypothesis 僅針對 `sanitize_telegram_html`）；離線戰報 near-miss fixtures（`near_miss_equity_pick_short`、`near_miss_five_tagged_news`）。CI 依賴補 [`hypothesis`](requirements-ci.txt)。
- **開源前檢查**：[docs/OPEN_SOURCE_CHECKLIST.md](docs/OPEN_SOURCE_CHECKLIST.md) 補齊 **本機清場清單**、`git filter-repo` 清 `.env.example` 歷史與 **清歷史後驗證**（gitleaks／TruffleHog）；並提醒除 XAI／OpenAI／Gemini／Telegram 外，曾出現在歷史中的其他 provider 亦須輪替。
- **Glassbox PWA（[`data-verification-ui/`](data-verification-ui/)）**：
  - 儀表板視覺：深底＋青綠／電紫層次、卡片與 metric 漸層、底欄毛玻璃（[`src/index.css`](data-verification-ui/src/index.css)）。
  - **`VITE_GLASSBOX_MOCK=1`**：今日戰情室與圖表頁示範資料（[`src/utils/mockToday.js`](data-verification-ui/src/utils/mockToday.js)、[`mockPerformance.js`](data-verification-ui/src/utils/mockPerformance.js)）。
  - **API 全失敗 fallback**：未設 mock 時，[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 在三支 API 皆錯且 loading 結束後自動載入示範 KPI／OPEN／QSREC。
  - **TradeCard**「展開 AI 決策邏輯」與 **Charts** 績效區骨架屏；靜態草圖 [`design/tradecard-ai-disclosure-mockup.html`](data-verification-ui/design/tradecard-ai-disclosure-mockup.html)。
- **CI**：[`.gitignore`](.gitignore) 例外 **`tests/fixtures/reports/**/expected_validation.json`**；補齊各 case 之 **`expected_validation.json`**（[`test_validate_report_fixtures.py`](test_validate_report_fixtures.py)）。
- **OSS 週期管線**：[`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py)（搜尋 → [`oss_repo_digest.py`](scripts/oss_repo_digest.py) → [`templates/oss_weekly_plan.md.j2`](templates/oss_weekly_plan.md.j2)）；[`scripts/oss_suitability.py`](scripts/oss_suitability.py) 啟發式適配度；合併勾選清單至 **`TODOS.md`**「OSS Scout 週報」區塊。
- **測試**：[test_oss_weekly.py](test_oss_weekly.py)。

### Changed
- **Gate 阻擋語意**：[report_html_gates.py](report_html_gates.py) 將「資料缺失標記過多」納入 `_BLOCKING_PREFIXES`，使 `blocking_issues` 與 `main.run_pipeline_with_retries` 分數型重試語意一致（`valid=False` 時一併視為結構阻擋）。
- **美股選股理由 Gate**：[report_html_gates.py](report_html_gates.py) `_EQUITY_PICK_KW` 以事件驅動語彙為主（核電、SMR、擴產、供電、液冷、良率等），並剔除易泛化之 IPO／產能／基礎設施／能源／電力等詞，避免惰性敘事繞過；[test_validate_report.py](test_validate_report.py) 迴歸對齊。
- **Telegram 模板**：[templates/telegram_report.j2](templates/telegram_report.j2) 進場／目標／停損欄位防禦性去除 AI 帶入的 `$`；失效欄位補 `replace('若', '')` 與既有「若／則失效。／。。」清洗，避免雙錢號與重複句讀。
- **Glassbox PWA**：導入 **Tailwind CSS**（[`tailwind.config.js`](data-verification-ui/tailwind.config.js) `preflight: false` + [`postcss.config.js`](data-verification-ui/postcss.config.js)、[`src/index.css`](data-verification-ui/src/index.css) `@tailwind utilities`）；[`TradeCard.jsx`](data-verification-ui/src/components/TradeCard.jsx) 改為玻璃擬態卡片、三欄價格網格、`isExpanded` 手風琴（觸發／失效／敘事）與防禦性 `N/A`；[`package.json`](data-verification-ui/package.json) 新增 `tailwindcss`／`postcss`／`autoprefixer`。
- **[`README.md`](README.md)**：War Room PWA 小節擴充為「最簡 mock／接 BQ／proxy 與 `VITE_API_URL`」分節；新手表新增 Glassbox 列。
- **[`crew.py`](crew.py)**：Crypto／AI 研究員預設拆成多個 **`async_execution=True`** 子任務（CrewAI 於 `Process.sequential` 內並行後收斂至審計與主編）；**`CREW_DISABLE_ASYNC_RESEARCH=1`** 回退單一 Grok 巨任務（見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）。[`main.py`](main.py) 雙 Crew 仍為既有 `ThreadPoolExecutor` 並行。
  - **Crypto**：`tasks` 順序 **`crypto_data_task` → `crypto_macro_task` → `crypto_news_task`**；宏觀任務僅經濟日曆／相關係數／估值錨／COT／灰階／歷史類比；**`sentiment_score_tool`**（或 `PIPELINE_SKIP_SENTIMENT_SCORE` 對應說明）改列**新聞子任務**可選區；新聞子任務另要求短呢喃與固定 `expected_output` 字串。
  - **AI**：**`ai_data_task`**（動能＋`financial_datasets` watchlist）與 **`ai_news_task`**（雙次 `market_search` + `newsapi`／`rss`／`gnews`／`rumor_scanner`）邊界分離；`review_task`／`final_report_task` 的 `context` 對齊兩（或三）個前驅輸出。
- **[`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)**：`SCOUT_SORT`、`SCOUT_PER_PAGE`、`--out-json`；預設 sort **stars**。
- **[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)**：每週一 UTC cron、`contents: write` push、artifact；`pip install jinja2`。
- **[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)**、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`TODOS.md`](TODOS.md) Direction 2B。

## 2026-03-28

### Added
- **[`tools_cache_http.py`](tools_cache_http.py)**：自舊 monolith 拆出 in-memory cache、`_http_get`、JSON 回應解析；[`tools_legacy.py`](tools_legacy.py)（經 `tools` 套件）轉發 `_CACHE`／`_CACHE_MAX_SIZE`／`_get_http_session` 供測試與相容。
- **錨定報告日**：環境變數 **`PIPELINE_REPORT_DATE`** — [`main.py`](main.py) 注入 exclusion 開頭；[`report_html_gates.py`](report_html_gates.py) 新聞新鮮度以該日 HKT 日末為參考時刻。
- **工具呼叫下限**：**`MIN_TOOL_CALLS_PER_PIPELINE`** + [`scratchpad.raw_tool_invocation_count`](scratchpad.py)（每次 `traced_tool_execution` 遞增）。
- **執行摘要 Gate（可選）**：**`STRICT_EXEC_SUMMARY_HTML_GATE`** — 正文須含【執行摘要】且至少 2 條要點。
- **Telegram「查看歷史」**：**`TELEGRAM_REPORT_HISTORY_URL`** — [`telegram_sender.py`](telegram_sender.py) 首則文字 chunk 附 Inline url 按鈕。
- **Web Push API 預留**：[`api.py`](api.py) `POST /api/push/subscribe`（預設 501；**`WEB_PUSH_ENABLED=1`** 時 200 noop）；CORS 允許 POST。
- **週期回測 workflow**：[`.github/workflows/weekly-backtest.yml`](.github/workflows/weekly-backtest.yml)（手動；`backtest.py --optimize --write-signal-weights`，需 `GCP_SA_KEY`）。
- **測試**：[test_api_push.py](test_api_push.py)、[`test_validate_report.py`](test_validate_report.py) `TestStrictExecSummaryHtmlGate`。

### Changed
- **產報效能預設**（[`main.py`](main.py)／[`crew.py`](crew.py)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）：`CREW_FUTURE_TIMEOUT_SEC` 預設 **2400**（40m）、`PIPELINE_HARD_DEADLINE_SEC` **13200**（3h40m，對齊 4h Cloud Run）；`BACKOFF_BASE_SEC` 預設 **25**；Gemini `max_retries` **4**。可選 **`PIPELINE_SKIP_SENTIMENT_SCORE=1`** 略過 `sentiment_score_tool` 以縮短加密段。
- **Gate 模組拆分**：[`report_html_gates.py`](report_html_gates.py) 承接原 `validate_report()`（HTML／環境變數／BigQuery）；結構化業務規則與 `ReportOutput`／`parse_report_output`／`assert_*` 收斂至 [`schemas.py`](schemas.py)（`DailyBriefReport` `@model_validator`）。已移除舊檔 `report_validator.py`、`report_output_validator.py`、`core/report_validation.py`、`check_report.py`。
- **[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)**：關閉 **`schedule` cron**（預設不再每 2 小時自動跑），僅保留 **`workflow_dispatch`**；要恢復排程可取消 YAML 內註解。[`README.md`](README.md) 表格已對齊。
- **[`TODOS.md`](TODOS.md)**：勾選與「已落地」對齊現況；新增 **階段 E** 長期索引（對 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)）。
- **[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)**：`PIPELINE_REPORT_DATE`、選幣輪動 staging 小節。
- **[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)**：鏈上 Tab／QSREC 頻率、`/api/push/subscribe`。
- **[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)**、[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`README.md`](README.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`crew.py`](crew.py)（候選多樣性一句）、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（METRIC 擴充）。
- **測試**：[`test_critical_paths.py`](test_critical_paths.py)、[`test_pipeline_observability_smoke.py`](test_pipeline_observability_smoke.py) 對齊 `_http_get`／`tools_cache_http._HTTP_SESSION`。
- **Telegram 讀者版精簡**：[`templates/telegram_report.j2`](templates/telegram_report.j2) 移除頂部 Source 三行；交易卡改四行（計畫／執行／敘事），風控與情境僅留結構化／QSREC。[`main.py`](main.py) 將 Source observability 與 Q-Score 改為僅 `logger.info`，不另發品質卡訊息；移除管線 `_maybe_editor_polish_html`（[`report_editor.py`](report_editor.py) 仍可供測試）。
- **Schema 文體與隱私**：[`schemas.py`](schemas.py) 新增 `internal_reasoning`（`TradeRecommendation`／`ExecutableTradeLeg`／`NewsItem`）、`narrative` few-shot 範例、標籤／指令洩漏清洗；[`QSREC_JSON_EXCLUDE_FIELDS`](schemas.py) 使對外 QSREC JSON 不含思考區；[`report_render.py`](report_render.py) 對齊 `model_dump` exclude。
- **Crew**：[`crew.py`](crew.py) 新增【機構級寫作｜Bloomberg 式】與【思考區 vs 展示區】；刪除未使用 `_POLISH_RULE`；幣圈 risk 任務 `expected_output` 對齊辯論結尾格式。

## 2026-03-27

### Changed
- **[`TODOS.md`](TODOS.md)**：pull 後重整——合併三大戰略方向與週次建議、**維護者執行意見**、**選幣／選股過於固定**橫切診斷與待辦；校正已落地項（`gate_failure_log`、`HIT_STOP` exclusion、`oss_scout` 腳本等）避免重複開票。
- **GitHub Actions runner 磁碟**：[`ci.yml`](.github/workflows/ci.yml)、[`deploy.yml`](.github/workflows/deploy.yml)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 於重步驟前執行 **Free disk space**（移除預裝 dotnet／android／CodeQL 等）；CI／monitor 的 `pip install` 改 **`--no-cache-dir`** 降低峰值；deploy 在 `docker push` 後 **`docker builder prune` / `system prune`**。緩解 `No space left on device` 與 runner 無法寫 `_diag` log。
- **GitHub Actions 分鐘數**：[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 改為每 **2** 小時排程、`pip install -r` [`requirements-monitor.txt`](requirements-monitor.txt)（僅 yfinance／BQ／Telegram，略過 CrewAI 全量依賴）；新增 `concurrency` 避免重疊 run；runner 對齊 `ubuntu-22.04`。

## 2026-03-26

### Added
- **啟動硬擋 `PIPELINE_STRICT_ENV`**：[`main._validate_critical_env_strict`](main.py) — `1` 且未 `SKIP_TELEGRAM`／`SKIP_BIGQUERY` 時分別要求 Telegram 與 GCP 專案＋憑證；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README`](README.md) 已註記。`NEWS_FRESHNESS_WINDOW_HOURS` 納入 [`_validate_env_types`](main.py) 數字校驗。
- **新聞新鮮度專項測試**：[`test_news_freshness.py`](test_news_freshness.py)；[`test_critical_paths.py`](test_critical_paths.py) 補 `_validate_critical_env_strict` 與錯誤 `NEWS_FRESHNESS_WINDOW_HOURS`。
- **Autoresearch／bench／營運文件**：[`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（尾端官方 `METRIC` 行 + 防偽註解）、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。
- **Backlog 規格補齊**：[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)、[`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md)；Scout 輔助腳本 [`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)（`GITHUB_TOKEN` 可選）。
- **Gate 失敗結構化日誌（自我改善資料基底）**：[`bigquery_writer.write_gate_failure_log`](bigquery_writer.py) 寫入 `{PROJECT}.market_data.gate_failure_log`（attempt、blocking/warning 計數、`bucket_counts_json`、`fingerprint`、`issues_preview` 等）；[`main.py`](main.py) 於 `run_pipeline_with_retries` 內每次 `validate_report` 有 `issues` 時呼叫。環境變數 **`GATE_FAILURE_BQ_LOG`**（預設開）、`SKIP_BIGQUERY=1` 時略過。測試：[`test_gate_failure_log.py`](test_gate_failure_log.py)。

### Changed
- **[`README.md`](README.md)**：重寫為較易掃描結構（開頭需求對照表、更新 mermaid、模組表含 editor／gate log／signal_weights／company crew、環境變數與觀測摘錄、`GATE_FAILURE_BQ_LOG`、輔助腳本與分組文件索引）；主線不依賴 X 與 `.cursorrules` 對齊。
- **`_check_news_freshness` 白名單行比對**：同時辨識 `YYYY-MM-DD HH:MM`／`YYYY/MM/DD`／`MM/DD` 等行內時間格式，避免戰報用 ISO 日期時 `NEWS_FRESHNESS_SOURCE_WHITELIST` 永不命中（[`report_html_gates.py`](report_html_gates.py)）。
- **Crew 管線**：自加密／AI 研究員 Agent 移除 `x_search_tool` 與相關 task 指令；與 [`.cursorrules`](.cursorrules)「廢棄 X/Twitter」一致，並減少每輪工具 schema 與 prompt token。
- **`main._prewarm_tool_caches`**：不再預熱 X 搜尋；啟動預熱並行數減 2。
- **`report_editor`**：精簡 system／user 指令字數，紅線與主編角色不變，降低潤稿 API 輸入 token。

### Removed
- **`_log_api_key_inventory`**：`TWITTER_BEARER_TOKEN` 列（管線不再使用；`tools.x_search_tool` 仍可供手動呼叫）。

## 2026-03-25

### Changed
- **[`TODOS.md`](TODOS.md)**：重整為全 repo 唯一待辦彙總——區分「已完成並驗證」「Backlog（BL-01…）」「ROADMAP 完成度矩陣」及靜態 repo 掃描紀錄；合併原條目、Autoresearch 計劃缺口與路線圖延伸項。

## 2026-03-21

### Fixed
- **`validate_report` / Gate**：新聞時區比對前剥除新聞行上 `<code>` 等行內 HTML，並接受 **HKT／香港時間** 等寫法；宏觀 **SOFR** 列若 SOFR 與匹配之 `%` 之間出現 **VIX／恐慌指數** 敘述則略過（避免將 VIX% 誤判為利率）；**美債** 行支援 **無冒號** 的 `10Y 報 x%` 格式；傳聞可信度增列 **信賴度／呢喃…可信度／置信分級／來源：…(B級)** 等模式。
- **戰報內容／版面**：後處理 **`_auto_prefix_missing_news_tags`** 對【核心新聞】之 `[日期 時間 UTC+8]` 行與【AI 產業新聞】之「標題 + 摘要：」自動補 **〔新聞 N〕**，避免計數永遠不足 6 則；**無 BigQuery 上期資料時仍剥除** LLM 捏造之【上期建議追蹤】；**`load_previous_recs_block`** 改為 `report_date + canon_asset + direction` 去重（同標的同向多筆只留一列）。

### Added
- **選幣／選股理由驗證**：`validate_report` 檢查加密與美股區「本日選擇理由」是否含足夠關鍵線索（催化/鏈上 vs 財報/新聞等）或退階說明，並是否點名 QSREC 內該類所有標的。交易觀望時略過；`STRICT_PICK_JUSTIFICATION=0` 關閉。
- **選幣／選股與昨日輪動**（`STRICT_PICK_ROTATION`，預設開）：若今日 QSREC 與昨日 BQ `RECOMMENDATIONS_TABLE` 之 **canonical 標的集合**完全相同且非空，理由須含 **重複選用理由** 等片語，否則驗證失敗；無 BQ／昨日無資料／查詢失敗則略過。`crew.py` 動態選幣／選股段落已註明此行為。
- **新聞 Gate 分級**：`validate_report` 將 **交易觀望**（`trade_watch_mode`）與 **新聞資料不足分段**（`partial_news_ok`）解耦；後者須 3~5 則〔新聞 N〕、〔新聞 1~3〕齊備、UTC+8 全過、且文內宣告不補虛構 + 【新聞資料狀態】或 `[REPORT_TIER:PARTIAL_NEWS]`（後處理在 3~5 則時自動注入）。環境變數 **`ALLOW_PARTIAL_NEWS_GATE`**（預設 `1`）可關閉分段。僅 **觀望模式** 等才放寬 R:R／勝率／投資解讀量化；僅分段不再因「出現新聞資料狀態」就放寬交易欄位。

### Changed
- **`tracker`**：`check_and_update_positions` 與 `load_previous_recs_block` 對多筆建議 **合併 Yahoo symbol 後批次 `yf.download`**，仍缺價之 symbol 再單檔 fallback，降低追蹤價格時的 HTTP 次數與限流風險。
- **`config.py` / `crew.py`**：LiteLLM 模型字串集中於 `config`（`MODEL_GROK`、`MODEL_GPT`、`MODEL_GEMINI`、`MODEL_CLAUDE`），可依環境變數覆寫；`OPENAI_MODEL` 仍為 GPT 慣用別名（優先於 `MODEL_GPT`）。
- **上期建議追蹤**：BigQuery 以 **canonical asset**（`$`/空白/`-` 正規化）做 `PARTITION BY`；`save_recommendations` 同日同標的只保留最後一筆；合併戰報後 **`main._inject_canonical_prev_recs_block`** 以 BQ 權威 HTML **覆寫** LLM 產出之【上期建議追蹤】，避免模型自行膨脹多列。
- **`validate_report`（STRICT_CONSISTENCY_GATE）**：宏觀異常僅在含 **美債** 之行解析 10Y/2Y；**SOFR** 僅解析關鍵字鄰近之利率 **%**（避免同列 VIX／敘事 % 誤判）。新聞時區接受 **GMT+8、全形加號、MM/DD/YYYY、可選秒數**，並在 **`【新聞資料狀態】` 行起**截斷後再比對〔新聞〕；計數前仍剔除【新聞資料狀態】等噪音行。傳聞可信度接受 **來源：B級**、**`可信度 72/100`**、**`等級：B`**、**`Grade: B`** 等。`_normalize_news_timezone_utc8` 與新聞時區規則對齊。
- **`crew`**：配對比值 LONG 與建倉敘事一致；AI 區強制〔新聞 4〕～〔新聞 6〕+ UTC+8；產業鏈呢喃需含可信度；加密區註明上期區塊後端可覆寫。

## 2026-03-20

### Changed
- **上期建議追蹤**（`tracker.load_previous_recs_block`）：同一 `report_date + asset` 以 `ROW_NUMBER` 去重，優先 `OPEN`、否則最新 `created_at`，避免同日多筆 QSREC 造成同標的多空重複列。
- **`validate_report`**：要求全篇至少 6 個 `〔新聞 N〕`；主 regime 為 neutral/risk_on 時禁止交易／風險預算段誤用「依 risk_off」等敘述；AI 儀表板區掃描常見幻覺欄位字串；美債 10Y/2Y 與「利差 %」口徑一致性檢查（約 10Y−2Y）。
- **後處理**：若注入後仍缺任一 `SourceHealth`/`SourceErrors`/`SourceQuota`，會再清一次殘行並重新注入完整區塊。
- **`crew`**：新聞強制 `〔新聞 1〕`…`〔新聞 6〕`（AI 區為 4–6）；AI 儀表板禁字清單加強；倉位示例避免 neutral 時寫「risk_off」。

## 2026-03-15

### Changed（GitHub Actions）
- **CI**（`ci.yml`）：`pull_request` 仍全跑；`push main` 僅在 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow 等路徑變更時跑 Lint+Test。
- **部署**（`deploy.yml`）：**移除** `push` 自動觸發，改為僅 **`workflow_dispatch`**（Actions → Run workflow）；執行時仍先 `workflow_call` `ci.yml` 再建映像與 Cloud Run Job 部署。
- `README.md`：同步說明「push 不自動部署、手動 Deploy workflow」。

## 2026-03-08

### Added
- 新增來源可觀測欄位：`SourceHealth`、`SourceErrors`、`SourceQuota`，並納入報告後處理與驗證規則。
- 新增來源健康分數機制（NewsAPI/GNews/Apify），支援 7 天半衰期，讓來源排序偏向近期穩定表現。
- 新增來源錯誤分類統計：`429`、`400`、`timeout`、`5xx`、`other`。
- 新增來源配額控管與成本保護：可設定每日上限，且依健康分數動態收斂可用配額。

### Changed
- `market_search_tool` 由固定 fallback 順序改為「健康分數驅動的動態來源優先序」。
- 報告 resilience 後處理強化：若缺少來源可觀測欄位，會自動注入固定區塊。
- `README.md` 更新為目前 agent 模型、工具組合、資料源策略與新環境變數。

### Persistence
- 來源健康狀態持久化升級：
  - 本地：`.source_health.json`
  - 雲端：BigQuery `source_health_stats`（可透過 `DISABLE_SOURCE_HEALTH_BQ=1` 關閉）

### Validation
- 已完成語法檢查、既有單元測試與 lint 檢查，未引入新錯誤。
