# Coding Conventions

## Style
- Follow Ruff guidelines (`ruff check .`). Prefer clean, readable, maintainable code.
- Resolve or document any existing warnings (unused variables, import order).

## Naming
- `snake_case` — functions and variables
- `PascalCase` — classes (e.g. `CryptoResearchCrew`, `AIResearchCrew`)
- `UPPER_SNAKE_CASE` — module-level constants
- Leading underscore — module-private names (e.g. `_get_cache`, `_CACHE`, `_is_retriable`)

## Error Handling
- Never swallow exceptions; log with `logging` (`logger.warning`, `logger.error`).
- Use retries + backoff for transient failures (503, 429, rate limits).
- Return `[DATA_MISSING:...]`-style messages from tools when APIs fail.

## Comments
- Document the "why" behind complex logic.
- Keep docstrings for public functions and non-obvious helpers.
- Use inline comments for business rules (e.g. thresholds, Telegram tag whitelist).

## Test-First Bug Fixes
- When a bug is reported, write a failing test FIRST. Then fix and prove it with a passing test.
