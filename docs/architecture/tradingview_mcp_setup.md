# TradingView MCP Repo-Side Bridge Setup

Status: optional sample only. The repository does not install a TradingView MCP server and does not edit `~/.claude`.

## Environment

```bash
TRADINGVIEW_MCP_ENABLED=0
TRADINGVIEW_MCP_COMMAND=
TRADINGVIEW_TIMEOUT_SEC=8
TRADINGVIEW_FALLBACK_YFINANCE=1
```

## Contract

- `tools/tradingview.py` calls `TRADINGVIEW_MCP_COMMAND <SYMBOL>` only when `TRADINGVIEW_MCP_ENABLED=1`.
- The command may print either plain text or JSON with fields such as `symbol`, `timeframe`, `signal`, `price`, `source`, or `summary`.
- When disabled, missing, timed out, or failed, the tool falls back to `multi_timeframe_tool`/yfinance if `TRADINGVIEW_FALLBACK_YFINANCE=1`; otherwise it returns `DATA_MISSING`.
- CI uses `MOCK_APIS=1` and `tests/fixtures/mock_data/tradingview.json`; no desktop app is required.

## Example Command Shape

```bash
python scripts/tradingview_mcp_bridge.py BTC
```

Example stdout:

```json
{"symbol":"BTC","timeframe":"1D","signal":"BUY","price":95000,"source":"tradingview_mcp"}
```
