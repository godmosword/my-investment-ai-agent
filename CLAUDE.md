# Project Developer Guide for Claude

## 1. Tooling & Navigation Rules (CRITICAL)
- **LSP Priority**: Strictly prioritize the LSP tool for all code navigation — finding definitions, references, and cross-file refactoring.
- **Avoid Text Search**: Do NOT use Grep, Glob, or Regex for code navigation unless LSP explicitly fails.

## 2. Project Context & Architecture
- **Description**: Q-Silicon Institutional Research AI Agent — a Python CrewAI pipeline that generates daily crypto & AI investment reports. Runs four agents (crypto researcher, AI researcher, risk critic, quant strategist), fetches real-time data, validates reports, then pushes to Telegram and writes metrics to BigQuery.
- **Tech Stack**: Python 3.11+; CrewAI + LiteLLM (multi-LLM: Grok, GPT, Claude, Gemini); Apify (search); Streamlit (dashboard); Google Cloud BigQuery; yfinance, pandas, plotly, matplotlib; pyTelegramBotAPI; python-dotenv, pydantic.

### Key Files (flat layout at repo root)
| File | Role |
|---|---|
| `main.py` | Entry point — retry loop, Telegram push, BigQuery write |
| `crew.py` | CrewAI agents & tasks definition |
| `tools.py` | Apify, CoinGlass, CryptoPanic, ML quant tools |
| `schemas.py` | Pydantic v2 schema — `DailyBriefReport`, `CryptoSection`, `AISection` |
| `config.py` | Constants: `PROJECT_ID`, `METRICS_TABLE`, `WHALE_TABLE`, model names |
| `report_render.py` | Assembles & renders final report from crew output |
| `report_validator.py` | Gate validation — blocking quality checks |
| `report_output_validator.py` | Output parsing & assertion helpers |
| `validation_rules.py` | Declarative validation rule definitions |
| `telegram_sender.py` | Telegram HTML sanitizer + send helpers |
| `bigquery_writer.py` | BigQuery insert helpers |
| `dashboard.py` | Streamlit war room |
| `visualizer.py` | Chart generation |
| `backtest.py` | ML backtesting |
| `tracker.py` | Signal/position tracker |
| `api.py` | FastAPI backend for PWA war room |
| `crew_output_parse.py` | Parses crew `kickoff()` output → Pydantic |
| `scratchpad.py` | Gate trace / debug JSONL writer |

### Sub-directories
| Dir | Contents |
|---|---|
| `core/` | `report_validation.py` — Phase 3 candidate validator entry point |
| `templates/` | `telegram_report.j2` — Jinja2 Telegram report template |
| `docs/` | Internal design docs (PHASE_GATES.md, REPORT_COMPARE_STAGING.md, etc.) |
| `data-verification-ui/` | Optional Vite + React PWA front-end |
| `.github/workflows/` | CI/CD: deploy + scheduler workflows |

## 3. Common Commands
- **Install deps**: `uv pip install -r requirements.txt --system`
- **Run tests (smoke, fast)**: `python3 -m pytest -m smoke -v`
- **Run full test suite**: `python3 -m pytest -v` (~140+ cases in `test_*.py` at root)
- **Lint**: `ruff check .`
- **Dashboard**: `streamlit run dashboard.py --server.port 8501 --server.headless true`
- **Full pipeline** (needs API keys, ~15–30 min): `python main.py`
- **Docker**: `docker build -f Dockerfile .`
- **Dual-track comparison**: `REPORT_COMPARE_MODE=1 python main.py` (see `docs/REPORT_COMPARE_STAGING.md`)

## 4. Bug Reporting & Fixing Workflow
- **Test-First**: When a bug is reported, first write a failing test that reproduces it. Then fix the bug and prove it with a passing test. Do NOT jump straight to fixing.

## 5. Coding Conventions
- **Style**: Ruff guidelines. Clean, readable, maintainable. Resolve existing warnings.
- **Naming**: `snake_case` functions/variables; `PascalCase` classes (e.g. `CryptoResearchCrew`); `UPPER_SNAKE_CASE` module constants; `_leading_underscore` for module-private names.
- **Error Handling**: Never swallow exceptions. Log with `logger.warning` / `logger.error`. Retry with backoff for 503/429. Return `[DATA_MISSING:...]`-style strings from tools when APIs fail.
- **Comments**: Document the "why", not the "what". Docstrings for public functions. Inline comments for business rules (thresholds, whitelist logic).

## 6. gstack — Web Browsing & Engineering Skills
- **Web Browsing**: Use `/browse` from gstack for ALL web browsing. NEVER use `mcp__claude-in-chrome__*` tools.
- **Setup** (first time per machine): `git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup`
- **If skills aren't working**: `cd ~/.claude/skills/gstack && ./setup`

Available skills: `/browse`, `/review`, `/ship`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/qa`, `/qa-only`, `/investigate`, `/retro`, `/codex`, `/office-hours`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/document-release`, `/setup-browser-cookies`.

See [`gstack.md`](gstack.md) for project-specific notes.
