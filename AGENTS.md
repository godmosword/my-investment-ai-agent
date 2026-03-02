# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Q-Silicon Institutional Research AI Agent — a Python-based CrewAI pipeline that generates daily crypto & AI investment reports. See `README.md` for full details.

### Key services

| Service | Command | Notes |
|---|---|---|
| Streamlit dashboard | `streamlit run dashboard.py --server.port 8501 --server.headless true` | Runs without API keys; shows N/A values without BigQuery credentials |
| Main pipeline | `python main.py` | Requires all LLM + data API keys (see README) |
| Backtest | `python backtest.py` | Requires BigQuery credentials for indicator data; BTC price from free CoinGecko API |

### Running the application

- **Streamlit dashboard** can start without any API keys or credentials. BigQuery-dependent widgets will display graceful fallback messages.
- **`python main.py`** requires 9+ API keys (4 LLM + 5 data APIs). Without them, CrewAI agents will fail. Telegram push is optional.
- All secrets are loaded via `python-dotenv` from a `.env` file in the project root, or from environment variables.

### Lint and checks

- No automated test suite exists in this repo. Validation is done via `validate_report()` in `main.py`.
- Linting: `ruff check .` — there are 2 pre-existing minor warnings (unused variable in `backtest.py`, import order in `crew.py`).
- Python version: the Dockerfile uses 3.11-slim, but the code runs fine on Python 3.12.

### Gotchas

- `pip install -r requirements.txt` installs to `~/.local` on this VM. Ensure `~/.local/bin` is on `PATH` (e.g. `export PATH="$HOME/.local/bin:$PATH"`) before running `streamlit` or `crewai` CLI commands.
- The project has no `pyproject.toml` or `setup.py` — it's a flat collection of Python scripts at the repo root.
- `crewai` pulls in many transitive dependencies (chromadb, opentelemetry, lancedb, etc.) which cause warnings about PATH but are non-blocking.

### Runtime observations (from live pipeline execution)

- **`python main.py` takes 15–30+ minutes** — the pipeline runs 4 sequential LLM agents (first 2 in parallel) with multiple tool calls and retries. This is expected.
- **LiteLLM `fastapi` warning** — LiteLLM logs `ImportError: No module named 'fastapi'` in its cold storage handler. This is a cosmetic warning and does **not** block LLM calls. Do not install `litellm[proxy]` unless you need the proxy server.
- **CryptoQuant MVRV Z-Score endpoint returns HTTP 404** — the `/v1/btc/market-data/mvrv-z-score` endpoint may have been removed or moved. The tool handles this gracefully and the pipeline continues.
- **BigQuery credentials setup** — when `GCP_SA_KEY` env var is available, write it to `~/.config/gcloud/sa-key.json` and set `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/sa-key.json` before running any Python commands. The service account needs **BigQuery Data Editor** + **BigQuery Job User** roles on the project.
- **Gemini model** (`gemini/gemini-3.1-pro-preview` in `crew.py`) — valid model per [Google AI docs](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview). May return 503 during high-demand periods; the pipeline's `max_retries=5` handles transient failures.
- **Data APIs confirmed working**: Tavily (news search), X/Twitter (tweet search), FRED (M2/DXY macro data), CoinGlass, CryptoQuant, and BigQuery (whale alerts + daily metrics read/write).
