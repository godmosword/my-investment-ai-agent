"""Local JSONL-backed Portfolio Tracker API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from portfolio_holdings import (
    add_holding,
    delete_holding,
    import_from_csv,
    load_holdings,
    update_holding,
)
from symbol_snapshot_service import fetch_symbol_quote

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _unprocessable(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("")
def get_portfolio() -> dict[str, list[dict[str, Any]]]:
    return {"holdings": load_holdings()}


@router.post("")
def create_holding(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return add_holding(body)
    except ValueError as exc:
        raise _unprocessable(exc) from exc


@router.patch("/{holding_id}")
def patch_holding(holding_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        updated = update_holding(holding_id, body)
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="holding not found")
    return updated


@router.delete("/{holding_id}")
def remove_holding(holding_id: str) -> dict[str, bool]:
    if not delete_holding(holding_id):
        raise HTTPException(status_code=404, detail="holding not found")
    return {"ok": True}


@router.post("/import")
async def import_holdings(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        raw = await file.read()
        csv_text = raw.decode("utf-8-sig")
        imported = import_from_csv(csv_text)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8") from exc
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    return {"imported": len(imported), "holdings": load_holdings()}


@router.get("/pnl")
def get_portfolio_pnl() -> dict[str, Any]:
    holdings = load_holdings()
    enriched: list[dict[str, Any]] = []
    total_value = 0.0
    total_pnl = 0.0
    total_day_pnl = 0.0

    for row in holdings:
        symbol = str(row.get("symbol") or "").strip().upper()
        try:
            quote = fetch_symbol_quote(symbol)
        except Exception:
            quote = {"error": "quote_unavailable", "last": None}
        last_price = quote.get("last")
        if quote.get("error") or last_price is None:
            enriched.append({**row, "symbol": symbol, "error": "quote_unavailable"})
            continue
        try:
            last = float(last_price)
        except (TypeError, ValueError):
            enriched.append({**row, "symbol": symbol, "error": "quote_unavailable"})
            continue

        shares = float(row.get("shares") or 0.0)
        cost_basis = float(row.get("cost_basis") or 0.0)
        market_value = shares * last
        cost = shares * cost_basis
        pnl = market_value - cost
        pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
        day_change_pct = quote.get("change_pct_1d")
        try:
            day_pnl = market_value * float(day_change_pct) / 100.0 if day_change_pct is not None else 0.0
        except (TypeError, ValueError):
            day_pnl = 0.0

        total_value += market_value
        total_pnl += pnl
        total_day_pnl += day_pnl
        enriched.append(
            {
                **row,
                "symbol": symbol,
                "last_price": last,
                "day_change_pct": day_change_pct,
                "market_value": market_value,
                "cost": cost,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "day_pnl": day_pnl,
            }
        )

    for row in enriched:
        if "market_value" in row and total_value > 0:
            row["weight"] = float(row["market_value"]) / total_value * 100.0
        elif "market_value" in row:
            row["weight"] = 0.0

    return {
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_day_pnl": total_day_pnl,
        "holdings": enriched,
    }
