# Reviewer Production Rollout Checklist

Queue 35 is an operational rollout, not a code switch. `USE_LANGGRAPH_ENGINE`
already defaults to `1`; this checklist verifies staging health before relying on
the reviewer path in production scheduling.

## Preconditions

- `USE_LANGGRAPH_ENGINE=1` in staging.
- `REVIEWER_LOG_BQ` points at the table created from `docs/SQL/reviewer_log.sql`.
- Optional LLM reviewer is explicit: `GRAPH_LLM_TRADE_REVIEWER=1` for LLM review,
  unset/`0` for deterministic reviewer only.
- Repo-side env ping (optional): `python3 scripts/verify_reviewer_rollout_env.py` (BQ table existence when creds present).
- Telegram HTML and `validate_report` gates remain enabled; reviewer never
  replaces those gates.

## Three-day staging watch

Run the normal scheduled pipeline for three report days, then check:

```bash
pytest test_reviewer_loop.py -m smoke
python3 -m pytest -m smoke
scripts/verify_graph_gate.sh
```

From the deployed API:

```bash
curl "$API_BASE/api/reports/qsrec-stats?days=7" \
  -H "X-Q-Silicon-Key: $QSILICON_MASTER_KEY"
```

Acceptance:

- `pass_rate_pct` is above 60% or each failure has an expected gate reason.
- Reviewer rows are written to BigQuery for every staging run.
- No increase in `GATE_EXECUTION_FAILED` without a corresponding fix note.
- War Room pipeline telemetry still emits node completion events.

## Production cutover

1. Confirm staging checks above are recorded in the deployment note.
2. Deploy with the same `USE_LANGGRAPH_ENGINE=1` and reviewer env values.
3. Watch first production run logs and `/api/reports/qsrec-stats?days=7`.
4. Roll back by setting `USE_LANGGRAPH_ENGINE=0` if reviewer failures block
   report delivery unexpectedly.

## Documentation updates

After cutover, update `TODOS.md` Queue 35 and add a same-day `CHANGELOG.md`
Ops entry with the staging dates and reviewer mode used.
