# ADR — Tool Platform & MOCK_APIS（Office Hours 2026-03-31）

**狀態**：Accepted（Phase 1 進行中）  
**來源**：`/office-hours` session；設計稿可於本機 gstack 路徑查閱：  
`~/.gstack/projects/godmosword-my-investment-ai-agent/godmosword-main-design-20260331-233613.md`  
**對齊**：[`TOOLS_MODULARIZATION_PLAN.md`](TOOLS_MODULARIZATION_PLAN.md)、[`TODOS.md`](../TODOS.md) 演進藍圖 Phase 1。

---

## 問題

管線依賴 8–12 支真實 API；fork 後無金鑰即難跑測試與驗證 Gate，不利開源貢獻與「可重現」宣稱。

## 目標

- **30 分鐘內可 fork**：`MOCK_APIS=1` 時可離線跑 smoke／擴充 fixtures。  
- **結構**：為後續 LangGraph／plugin marketplace 預留邊界，避免在單一巨檔堆 mock 分支。

## 決策：**Alt B — Ideal Architecture First**

- **否決 Alt A**：在既有 3k+ 行 `tools_legacy` 內聯 mock，未來難拆、貢獻者難學規約。  
- **否決 Alt C（eval arena 先做）**：replay 需先有 mock 與凍結資料，屬 Phase 2。

## 實作方向（分階）

| 階段 | 內容 |
|------|------|
| **Phase 1a（本 ADR 落地起點）** | `tools/` 套件；`tools_legacy.py` 保留全部 `@tool`；`tools/__init__.py` star re-export；`tools.base`（`MOCK_APIS`、`load_mock_json`）；`tools.market`（fixture 橋接）；`tests/fixtures/mock_data/market.json`。 |
| **Phase 1b** | 逐工具搬離 `tools_legacy` → `tools/market.py` 等，每步 smoke。 |
| **Phase 2** | CI：`MOCK_APIS=1`、`SKIP_BIGQUERY=1`、`SKIP_TELEGRAM=1` 跑 PR smoke（與現有 `conftest` stub 對齊，避免雙重 mock）。 |
| **Phase 3** | `docker-compose.yml`：`MOCK_APIS=1` 乾跑管線。 |
| **Phase 4** | README「Fork in 5 minutes」。 |

## 後果

- **Import**：`from tools import fear_greed_tool` 等**不變**（經 `tools` 套件 re-export）。  
- **新工具**：優先在子模組實作，並沿用專案紅線（`_get_cache` / `_set_cache`、無捏造數字）。  
- **文件**：根目錄不再使用檔名 `tools.py`；敘述改為「`tools` 套件 + `tools_legacy`」。

## 連結

- [TOOLS_MODULARIZATION_PLAN.md](TOOLS_MODULARIZATION_PLAN.md)  
- [ENV_TEMPLATE.txt](../ENV_TEMPLATE.txt) — `MOCK_APIS`  
