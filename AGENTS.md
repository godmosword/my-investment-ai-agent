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
