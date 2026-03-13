# Project Developer Guide for Claude

## 1. Tooling & Navigation Rules (CRITICAL)
- **LSP Priority**: You MUST strictly prioritize using the Language Server Protocol (LSP) tool for all code navigation tasks, including finding definitions, finding references, and cross-file refactoring.
- **Avoid Text Search**: Do NOT use standard text search tools (like Grep, Glob, or Regex) for code navigation unless the LSP tool explicitly fails or is entirely unavailable for the target file type.
- **Efficiency**: Utilize the sub-50ms search capabilities of LSP to quickly understand project structure before making modifications.

## 2. Project Context & Architecture
- **Tech Stack**: Python 3.11+; CrewAI + LiteLLM (multi-LLM: Grok, GPT, Claude, Gemini); Apify (search); Streamlit (dashboard); Google Cloud BigQuery (metrics & whale data); yfinance, pandas, plotly, matplotlib (data & charts); pyTelegramBotAPI (push); python-dotenv, pydantic. Optional sub-project: `data-verification-ui/` (Vite + React).
- **Description**: Q-Silicon Institutional Research AI Agent — a Python-based CrewAI pipeline that generates daily crypto & AI investment reports. It runs four specialized agents (crypto researcher, AI researcher, risk critic, quant strategist), fetches real-time data (Apify, CoinGlass, CryptoPanic, BigQuery), validates and retries report generation, then pushes to Telegram, writes metrics to BigQuery, and serves a Streamlit war room plus optional chart generation.
- **Structure**: Flat Python scripts at repo root: `main.py` (entry, retry, Telegram, BigQuery), `crew.py` (CrewAI agents & tasks), `tools.py` (Apify, CoinGlass, CryptoPanic, ML quant, etc.), `config.py` (PROJECT_ID, METRICS_TABLE, WHALE_TABLE), `dashboard.py` (Streamlit), `visualizer.py` (charts), `backtest.py` (ML backtest), `backfill_data.py` (historical backfill). Config: `requirements.txt`, `.env` / `ENV_TEMPLATE.txt`. CI/CD: `.github/workflows/` (deploy, scheduler). Optional front-end: `data-verification-ui/`.

## 3. Common Commands
- **Install Dependencies**: `pip install -r requirements.txt` (or `pip3 install -r requirements.txt` / `python3 -m pip install -r requirements.txt`; ensure `~/.local/bin` on PATH for streamlit).
- **Run Development Server**: `streamlit run dashboard.py --server.port 8501 --server.headless true` (dashboard; no API keys required for startup; BigQuery widgets show fallbacks without credentials).
- **Run Tests**: No automated test suite. Validation is done via `validate_report()` in `main.py`. For lint only: `ruff check .`
- **Build**: No traditional build step. For container: `docker build -f Dockerfile .` (see `Dockerfile` / `docker-compose.yml`). Main pipeline run: `python main.py` (requires LLM + data API keys; takes ~15–30+ minutes).

## 4. Bug Reporting & Fixing Workflow
- **Test-First Bug Fixes**: When a bug is reported, do NOT start by trying to fix it. Instead, first write a test that reproduces the bug. Then, have subagents try to fix the bug and prove it with a passing test.

## 5. gstack — Web Browsing & Engineering Workflow Skills
- **Web Browsing**: Use the `/browse` skill from gstack for ALL web browsing tasks. NEVER use `mcp__claude-in-chrome__*` tools.
- **Available skills**:
  - `/plan-ceo-review` — CEO-level review of a plan or proposal
  - `/plan-eng-review` — Engineering review of a plan or technical design
  - `/review` — Code review
  - `/ship` — Ship / merge a feature
  - `/browse` — Headless web browsing (use this instead of Chrome MCP tools)
  - `/retro` — Retrospective on a completed task or sprint

## 6. Coding Conventions
- **Style**: Follow standard Ruff guidelines (`ruff check .`). Prefer clean, readable, maintainable code; resolve or document any existing warnings (e.g. unused variables, import order).
- **Naming**: Use `snake_case` for functions and variables; `PascalCase` for classes (e.g. `CryptoResearchCrew`, `AIResearchCrew`); `UPPER_SNAKE_CASE` for module-level constants; leading underscore for module-private names (e.g. `_get_cache`, `_CACHE`, `_is_retriable`).
- **Error Handling**: Implement robust error handling. Do not swallow exceptions; log them with `logging` (e.g. `logger.warning`, `logger.error`). Use retries and backoff for transient failures (503, 429, rate limits); return clear `[DATA_MISSING:...]`-style messages from tools when APIs fail.
- **Comments**: Document complex logic and the "why" behind decisions. Keep docstrings for public functions and non-obvious helpers; use inline comments for business rules (e.g. thresholds, Telegram tag whitelist).
