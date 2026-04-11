# Contributing to Q-Silicon

## Quick start

1. Copy [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) to `.env` and fill API keys for the paths you need (see [`README.md`](README.md)).
2. Install dependencies: `pip install -r requirements.txt` (CI uses [`requirements-ci.txt`](requirements-ci.txt)).
3. Run checks before pushing: `ruff check .` and `python3 -m pytest -m smoke -v`.

## Pull requests

- Prefer small, reviewable commits with clear messages.
- Do not weaken the project red lines in [`.cursorrules`](.cursorrules): no fabricated prices, Telegram HTML whitelist, `validate_report` contracts, and `main.py` threading safety for dual crews.
- User-visible behavior changes should be noted in [`CHANGELOG.md`](CHANGELOG.md).

## Questions

See [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md) for architecture and collaboration norms.
