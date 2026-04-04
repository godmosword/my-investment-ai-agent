# Project Developer Guide for Claude

**Claude Code** discovers this file at the repo root as project context; **Cursor** loads `.cursor/rules/claude-md-bootstrap.mdc` + `.cursorrules` §0 so agents are nudged to read this file before substantive work.

Concise orientation for coding agents. **Authoritative product/README detail** → [`README.md`](README.md). **Backlog & shipped features** → [`TODOS.md`](TODOS.md). **Human changelog** → [`CHANGELOG.md`](CHANGELOG.md). **Cursor-specific** → [`AGENTS.md`](AGENTS.md) (includes **Collaboration model / Technical Co-Founder** alignment for agent–human roles).

---

## 1. Tooling & Navigation Rules (CRITICAL)

- **LSP priority**: Prefer the IDE/LSP for go-to-definition, references, and refactors.
- **Fallback**: If LSP is unavailable, targeted search (e.g. ripgrep) is acceptable—do not avoid navigation entirely.

---

## 2. Project Red Lines (Q-Silicon)

Align with [`.cursorrules`](.cursorrules) and [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md):

- **No data hallucination**: Objective prices, indicators (RSI, MAs, VIX, etc.), and macro figures must come from **Python tools** / APIs injected into context—not LLM invention.
- **X/Twitter**: Not used in the main daily pipeline (crew tasks do not rely on X search); do not reintroduce it as a primary news path.
- **Telegram HTML**: Whitelist only `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<blockquote>`, `<a>`. Report layout order: dashboard → core news → market murmurs → actionable trades.
- **Tools**: New tools should implement cache helpers consistent with existing patterns (`_get_cache` / `_set_cache` where applicable).
- **Threading**: Respect `ThreadPoolExecutor` safety for the dual crypto + AI crew path in [`main.py`](main.py).

---

## 3. Project Context & Architecture

- **Description**: Q-Silicon Institutional Research AI Agent — Python **CrewAI** pipeline producing daily **crypto** and **AI (incl. US equities fundamentals)** research, merged into a Telegram HTML brief. Optional **LLM judge**, **BigQuery** metrics / logs, **Streamlit** dashboard, **FastAPI** + **PWA** front-end.
- **Flow (high level)**: API key checks → optional strict env → numeric env validation → tool prewarm → **parallel** `CryptoResearchCrew` + `AIResearchCrew` → assemble/render → `validate_report` / structured validation → optional editor polish → Telegram + BQ writes.
- **Tech stack**: Python 3.11+ (Dockerfile 3.11-slim; 3.12 OK locally); CrewAI + LiteLLM (Grok, GPT, Claude, Gemini); Streamlit; BigQuery; pandas / plotly / matplotlib; pyTelegramBotAPI; pydantic v2; python-dotenv.

### Key files (repo root)

| File | Role |
|------|------|
| [`main.py`](main.py) | Entry: `_validate_required_keys`, `_validate_critical_env_strict` (`PIPELINE_STRICT_ENV`), `_validate_env_types`, prewarm, dual-crew run, retries, Telegram, BQ, charts |
| [`crew.py`](crew.py) | CrewAI agents, tasks, LLM fallback chains |
| [`tools/`](tools/) + [`tools_legacy.py`](tools_legacy.py) | Crew import `tools` (package re-exports legacy); new scaffold `tools.base` / `tools.market` + ADR [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md); split plan [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md) |
| [`schemas.py`](schemas.py) | Pydantic — `DailyBriefReport`, sections, QSREC |
| [`config.py`](config.py) | `PROJECT_ID`, table IDs, model env names, `GATE_FAILURE_LOG_TABLE`, etc. |
| [`report_render.py`](report_render.py) | Assemble + render Telegram HTML from crew output |
| [`report_html_gates.py`](report_html_gates.py) | HTML/env/BQ gate: `validate_report()` (news, UTC+8, freshness, QSREC, rotation, …) |
| [`schemas.py`](schemas.py) | Pydantic contract + `ReportOutput` / `parse_report_output` + `validate_structured_report` + `DailyBriefReport` business rules |
| [`report_judge.py`](report_judge.py) | Hard-pattern judge; optional `REPORT_LLM_JUDGE` |
| [`report_editor.py`](report_editor.py) | Optional polish pass (`EDITOR_AGENT_ENABLED`) |
| [`validation_rules.py`](validation_rules.py) | Shared regex / rule fragments for validation |
| [`telegram_sender.py`](telegram_sender.py) | HTML sanitization + send helpers |
| [`bigquery_writer.py`](bigquery_writer.py) | Metrics, LLM run log, exclusion context, **`write_gate_failure_log`** |
| [`tracker.py`](tracker.py) | Positions / previous recommendations |
| [`scratchpad.py`](scratchpad.py) | JSONL trace, tool caps, editor/judge append |
| [`api.py`](api.py) | FastAPI for PWA / war room data |
| [`api_schema.py`](api_schema.py) | JSON response guards for tools |
| [`dashboard.py`](dashboard.py) | Streamlit war room |
| [`crew_output_parse.py`](crew_output_parse.py) | Crew `kickoff()` output → Pydantic |
| [`signal_weights_store.py`](signal_weights_store.py) | Versioned ML weights; optional crew context (`WEIGHTS_CONTEXT_ENABLED`) |
| [`crew_company.py`](crew_company.py) | Company Growth narrative pilot (`COMPANY_CREW_ENABLED`) |
| [`company_ops_schemas.py`](company_ops_schemas.py) | Pydantic schemas for company ops / war room |
| [`monitor_intraday.py`](monitor_intraday.py) | Intraday monitor script + workflow companion |
| [`visualizer.py`](visualizer.py) | Chart generation |
| [`backtest.py`](backtest.py) | ML backtest CLI |

### Subdirectories

| Path | Contents |
|------|----------|
| [`core/`](core/) | Reserved package root (`__init__.py`); compare path uses `main._validate_report_candidate` → `report_html_gates.validate_report` |
| [`templates/`](templates/) | `telegram_report.j2` |
| [`docs/`](docs/) | Design docs, runbooks, SQL samples (see §5) |
| [`scripts/`](scripts/) | `bench_autoresearch.sh`, `oss_scout_candidates.py`, `write_ml_weights.py`, `inject_test_data.py` |
| [`data-verification-ui/`](data-verification-ui/) | Vite + React PWA |
| [`.github/workflows/`](.github/workflows/) | CI, deploy (`environment: production`), schedulers |

---

## 4. Common Commands

| Task | Command |
|------|---------|
| Install deps | `uv pip install -r requirements.txt --system` or `pip install -r requirements.txt` |
| Lint | `ruff check .` |
| Smoke tests (CI-aligned) | `python3 -m pytest -m smoke -v`（Actions 使用 [`requirements-ci.txt`](requirements-ci.txt) + `conftest` stub） |
| Full tests | `python3 -m pytest -v`（nightly workflow 每日 full；deploy 前僅 smoke） |
| Boundary / contract subset | `python3 -m pytest -m boundary -v`（markers 見 [`pytest.ini`](pytest.ini)；矩陣見 [`docs/BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md)） |
| Dashboard | `streamlit run dashboard.py --server.port 8501 --server.headless true` |
| Full pipeline | `python main.py` (many API keys; ~15–30+ min) |
| Dry run | `SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py` |
| Strict prod-like startup | `PIPELINE_STRICT_ENV=1` (requires Telegram and/or GCP when respective `SKIP_*` unset) |
| Bench / autoresearch hook | `./scripts/bench_autoresearch.sh` (ruff + smoke; official `METRIC` lines at end only) |
| Docker | `docker build -f Dockerfile .` |
| Dual-track compare | `REPORT_COMPARE_MODE=1 python main.py` — [`docs/REPORT_COMPARE_STAGING.md`](docs/REPORT_COMPARE_STAGING.md) |

---

## 5. Documentation Index (`docs/`)

| Doc | Purpose |
|-----|---------|
| [`DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) | Brief format / Telegram rules |
| [`BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md) | Gate／HTTP／main 邊界測試盤點與 pytest marker |
| [`research/LAST30DAYS_SKILL.md`](docs/research/LAST30DAYS_SKILL.md) | 可選 [last30days-skill](https://github.com/mvanhorn/last30days-skill)：安裝、pilot、與日報管線信任邊界（預設 A+B，不進 `main.py`） |
| [`ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) | Product directions |
| [`DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) | Streamlit / API / PWA KPI contract |
| [`DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) | Production deploy + GitHub Environment reviewers |
| [`AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md) + [`autoresearch.plan.md`](docs/autoresearch.plan.md) | Autoresearch loop spec |
| [`REPORT_COMPARE_STAGING.md`](docs/REPORT_COMPARE_STAGING.md) | Compare mode |
| [`COST_PER_MODEL.md`](docs/COST_PER_MODEL.md) | LLM cost notes |
| [`COMMERCE_PLAYBOOK.md`](docs/COMMERCE_PLAYBOOK.md) / [`COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md) | Commerce hypotheses / checklist |
| [`COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md) | Multi-function crew roadmap |
| [`TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md) | Splitting legacy tools |
| [`ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) | MOCK_APIS / `tools` package (Office Hours Alt B) |
| [`SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql) | Example BQ aggregation for gate failures |
| [`oss_candidates/README.md`](docs/oss_candidates/README.md) | OSS scout process |

**Env reference**: [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) (copy to `.env`).

---

## 6. Observability & Gates (quick reference)

- **Gate failure artifacts**: `.qsilicon/last_gate_failure/` when `GATE_FAILURE_ARTIFACTS` enabled.
- **Gate failure BigQuery**: `write_gate_failure_log` → `{PROJECT}.market_data.gate_failure_log`; toggle `GATE_FAILURE_BQ_LOG`, respect `SKIP_BIGQUERY`.
- **Scratchpad**: `.qsilicon/scratchpad/*.jsonl` when `SCRATCHPAD_ENABLED`.
- **News freshness** (optional): `STRICT_NEWS_FRESHNESS_GATE`, `NEWS_FRESHNESS_WINDOW_HOURS`, `NEWS_FRESHNESS_SOURCE_WHITELIST` — see [`report_html_gates.py`](report_html_gates.py), tests in [`test_news_freshness.py`](test_news_freshness.py).
- **投資解讀 vs 儀表板**（optional, default off）: `STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE=1` — 每則投資解讀的數字錨點須出現在同段區塊① `<code>` 讀值；觀望模式略過；blocking。

---

## 7. Bug Fixing Workflow

- **Test-first**: Add a failing test that reproduces the bug, then fix until green. Do not fix-only without coverage for regressions.

---

## 8. Coding Conventions

- **Style**: Ruff; fix warnings in touched files.
- **Naming**: `snake_case` / `PascalCase` / `UPPER_SNAKE_CASE` / `_private`.
- **Errors**: Log with `logger.warning` / `logger.error`; retry 503/429 with backoff where appropriate; tools return `[DATA_MISSING:...]` (or agreed sentinel) on API failure—do not silently return fake numbers.
- **Comments**: Explain *why*; docstrings on public APIs; inline notes for thresholds and whitelist behavior.

---

## 9. gstack — Browsing & Workflow Skills

- **Optional social/trend research (not daily pipeline data)**: [last30days-skill](https://github.com/mvanhorn/last30days-skill) — install per upstream; scope and red-line alignment → [`docs/research/LAST30DAYS_SKILL.md`](docs/research/LAST30DAYS_SKILL.md).
- **Browsing**: Prefer `/browse` from gstack for interactive web QA when applicable. Do not use legacy `mcp__claude-in-chrome__*` flows documented as deprecated in older setups.
- **Setup** (first time): `git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup`
- **Skills** (examples): `/browse`, `/review`, `/ship`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/qa`, `/qa-only`, `/investigate`, `/retro`, `/codex`, `/office-hours`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/document-release`, `/setup-browser-cookies`.

See [`gstack.md`](gstack.md) if present for repo-local gstack notes.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
