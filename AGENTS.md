# AGENTS.md

## Cursor Cloud specific instructions

### Before you code (read this repo’s guide)

- On **first task** in this repo or when **starting a large change**, read root **`CLAUDE.md`** first (architecture map, commands, `docs/` index, project red lines). Then `README.md` / `ENV_TEMPLATE.txt` for detail; **`TODOS.md`** for backlog.

### Collaboration model (Technical Co-Founder alignment)

Adapted from a product-building prompt framework (Miles Deutscher / AIEDGE), scoped to this repo:

- **Product owner**: The human owns scope and trade-offs; agents implement, explain options, and surface risks (data trust, gates, regressions).
- **Phased work**: Prefer clarifying needs and a short plan before large diffs; ship in reviewable slices. Do not replace `validate_report` / Pydantic contracts with vague prose.
- **Push back**: Flag requests that would weaken no-hallucination rules, the Telegram HTML whitelist, or `ThreadPoolExecutor` safety; propose smaller, compliant alternatives.
- **Two audiences**: Engineering discussion in Cursor may use normal technical terms. **Reader-facing brief** text stays institutional and data-dense per [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) and crew stylistic rules—no tutorial tone (“what is VIX”) for professional readers.
- **Handoff**: Ship with meaningful commits; update [`CHANGELOG.md`](CHANGELOG.md) for user-visible behavior and **keep [`TODOS.md`](TODOS.md) in sync** (delivered summary, queue, revision log — bidirectional rule in both files’ headers); refresh [`CLAUDE.md`](CLAUDE.md) / [`README.md`](README.md) when commands or navigation change.

### Git / ship workflow（本 repo 預設）

- **縮短流程**：變更就緒後優先 **`git push origin main`**（在 `main` 上 commit，或先 `merge` 回 `main` 再推），以觸發 [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) 的 `push` 部署；**不要**自動執行 `gh pr create`，除非使用者明確要 PR、或 **GitHub branch protection** 禁止直推 `main`（此時改走 PR 並說明原因）。
- **合併前**：本地仍應跑與 CI 對齊的檢查（例如 `ruff check .`、`pytest -m smoke`），與是否開 PR 無關。

### Project overview

Q-Silicon Institutional Research AI Agent — a Python-based CrewAI pipeline that generates daily crypto & AI investment reports. See `README.md` for full details.

### Key services

| Service | Command | Notes |
|---|---|---|
| Streamlit dashboard | `streamlit run dashboard.py --server.port 8501 --server.headless true` | Runs without API keys; shows N/A values without BigQuery credentials. **v3 UI**: dark gradient shell, unified Plotly hover/legend, gauge bands aligned with Risk ON / Neutral / Risk OFF (2.5 / 3.5 thresholds). |
| Main pipeline | `python main.py` | Requires all LLM + data API keys (see README) |
| Backtest | `python backtest.py` | Requires BigQuery credentials for indicator data; BTC price from free CoinGecko API |

### Running the application

- **Streamlit dashboard** can start without any API keys or credentials. BigQuery-dependent widgets will display graceful fallback messages.
- **`python main.py`** requires 9+ API keys (4 LLM + 5 data APIs). Without them, CrewAI agents will fail. Telegram push is optional.
- All secrets are loaded via `python-dotenv` from a `.env` file in the project root, or from environment variables.

### Lint and checks

- **Automated tests**: `pytest` at repo root (`test_*.py`). **PR checks** (`.github/workflows/ci.yml`): `ruff check .` + `pytest -m smoke` with [`requirements-ci.txt`](requirements-ci.txt) (lighter than full `requirements.txt`; see `conftest.py` stubs). **Deploy** reuses `ci.yml` with **smoke only**; **full** `pytest -v` runs in [`nightly-ci.yml`](.github/workflows/nightly-ci.yml) (schedule + manual). Runtime validation of daily reports is still `validate_report()` in `main.py` (6 news tags by default; **partial news** = 3–5 tags with 〔新聞 1–3〕+ UTC+8 + no-fake-news declaration + optional `[REPORT_TIER:PARTIAL_NEWS]`; `ALLOW_PARTIAL_NEWS_GATE=0` disables. **Trade-field** relax (R:R, etc.) only under **trade watch** phrases, not from news footer alone).
- Linting: `ruff check .` — there may be minor pre-existing warnings in some files; fix when touching those files.
- Python version: the Dockerfile uses 3.11-slim, but the code runs fine on Python 3.12.

### Gotchas

- `pip install -r requirements.txt` installs to `~/.local` on this VM. Ensure `~/.local/bin` is on `PATH` (e.g. `export PATH="$HOME/.local/bin:$PATH"`) before running `streamlit` or `crewai` CLI commands.
- The project has no `pyproject.toml` or `setup.py` — it's a flat collection of Python scripts at the repo root.
- `crewai` pulls in many transitive dependencies (chromadb, opentelemetry, lancedb, etc.) which cause warnings about PATH but are non-blocking.
- `hypothesis` is listed in `requirements-ci.txt` but **not** in `requirements.txt`. The full test suite (`pytest -v`) includes `test_boundary_hypothesis.py` which imports it, so install `hypothesis` separately (`pip install hypothesis`) for local full-suite runs.
- The React PWA (`data-verification-ui/`) has **no lockfile** — use `npm install` (not yarn/pnpm). Start with `VITE_GLASSBOX_MOCK=1 npm run dev` to see mock data without a backend.

### Runtime observations (from live pipeline execution)

- **`python main.py` takes 15–30+ minutes** — the pipeline runs 4 sequential LLM agents (first 2 in parallel) with multiple tool calls and retries. This is expected.
- **LiteLLM `fastapi` warning** — LiteLLM logs `ImportError: No module named 'fastapi'` in its cold storage handler. This is a cosmetic warning and does **not** block LLM calls. Do not install `litellm[proxy]` unless you need the proxy server.
- **CryptoQuant MVRV Z-Score endpoint returns HTTP 404** — the `/v1/btc/market-data/mvrv-z-score` endpoint may have been removed or moved. The tool handles this gracefully and the pipeline continues.
- **BigQuery credentials setup** — when `GCP_SA_KEY` env var is available, write it to `~/.config/gcloud/sa-key.json` and set `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/sa-key.json` before running any Python commands. The service account needs **BigQuery Data Editor** + **BigQuery Job User** roles on the project.
- **Gemini model**（預設 `gemini/gemini-2.5-pro`，`MODEL_GEMINI` 可覆寫）— 見 [Gemini 2.5 Pro](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-pro)。高峰期仍可能 503；管線 `max_retries=5` 處理暫態失敗。
- **Data APIs**: Tavily、FRED、CryptoQuant、BigQuery 等見各工具實作。日報 Crew **已不掛載** `x_search_tool`（`.cursorrules`）；`tools.py` 仍保留該函式供本機手動。**CoinGlass** 見下方專節（v4 與方案權限）。

### CoinGlass API v4（對照官方文件）

- **Base URL**：`https://open-api-v4.coinglass.com`（與 [官方文件](https://docs.coinglass.com/reference/authentication) 一致）。
- **認證**：Header `CG-API-KEY: <COINGLASS_API_KEY>`（`tools.py` 中 `coinglass_data_tool`、ETF 等 v4 呼叫皆如此）。
- **成功回應**：JSON 內 `code` 為字串 `"0"` 或整數 `0`；否則為錯誤（常見 `code: "401"`, `msg: "Upgrade plan"`）。
- **401 / Upgrade plan**：代表金鑰已送出且被辨識，但**目前訂閱方案不含該端點**或需升級，非 URL 拼錯。請對照 [CoinGlass 方案](https://www.coinglass.com/pricing)。失敗時管線會 **warning 日誌**（`code`/`msg`/metric）並對 **BTC** 等指標走 **Binance 公開 API 備援**（見 `tools.py`）。
- **`regime_scorecard_tool`**：24h 爆倉僅走 **v4** `GET .../api/futures/liquidation/history`（`CG-API-KEY`），與 `coinglass_data_tool` 一致；無 v2 / `coinglassSecret`。
- **本機測試 curl**（須在同一 shell `source .env`，勿用子 shell 包 `(. ./env)`，否則金鑰傳不進 `curl`）：
  ```bash
  set -a && . ./.env && set +a
  curl -s "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d&limit=1" \
    -H "accept: application/json" -H "CG-API-KEY: $COINGLASS_API_KEY" | python3 -m json.tool
  ```
