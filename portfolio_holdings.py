"""Local JSONL-backed portfolio holdings store.

This store is intentionally small and deterministic: callers read the full file,
derive a new list, then atomically rewrite it. It is for Portfolio Tracker v1,
not broker integration.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


CSV_COLUMNS = ["symbol", "shares", "cost_basis", "opened_at", "notes"]


class _QueryParam:
    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value


def _store_path() -> Path:
    raw = (os.getenv("PORTFOLIO_HOLDINGS_FILE") or "portfolio_holdings.jsonl").strip()
    return Path(raw).expanduser()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper().lstrip("$")
    if not symbol or any(ch.isspace() for ch in symbol):
        raise ValueError("symbol must be a non-empty uppercase string")
    return symbol


def _parse_positive_float(value: Any, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be > 0")
    return parsed


def _parse_nonnegative_float(value: Any, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be >= 0")
    return parsed


def _normalize_date(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("opened_at must be YYYY-MM-DD") from exc


def _normalize_create_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": _normalize_symbol(data.get("symbol")),
        "shares": _parse_positive_float(data.get("shares"), "shares"),
        "cost_basis": _parse_nonnegative_float(data.get("cost_basis"), "cost_basis"),
        "opened_at": _normalize_date(data.get("opened_at")),
        "notes": str(data.get("notes") or "").strip(),
    }


def _normalize_patch_payload(patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "shares" in patch:
        out["shares"] = _parse_positive_float(patch.get("shares"), "shares")
    if "cost_basis" in patch:
        out["cost_basis"] = _parse_nonnegative_float(patch.get("cost_basis"), "cost_basis")
    if "opened_at" in patch:
        out["opened_at"] = _normalize_date(patch.get("opened_at"))
    if "notes" in patch:
        out["notes"] = str(patch.get("notes") or "").strip()
    return out


def load_holdings() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def save_holdings(holdings: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for row in holdings:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def add_holding(data: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    holding = {
        "id": str(uuid.uuid4()),
        **_normalize_create_payload(data),
        "created_at": now,
    }
    holdings = [*load_holdings(), holding]
    save_holdings(holdings)
    return holding


def update_holding(id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    holding_id = str(id or "").strip()
    if not holding_id:
        return None
    normalized_patch = _normalize_patch_payload(patch)
    holdings = load_holdings()
    next_holdings: list[dict[str, Any]] = []
    updated: dict[str, Any] | None = None
    for row in holdings:
        if row.get("id") == holding_id:
            updated = {**row, **normalized_patch}
            next_holdings.append(updated)
        else:
            next_holdings.append(row)
    if updated is None:
        return None
    save_holdings(next_holdings)
    return updated


def delete_holding(id: str) -> bool:
    holding_id = str(id or "").strip()
    if not holding_id:
        return False
    holdings = load_holdings()
    next_holdings = [row for row in holdings if row.get("id") != holding_id]
    if len(next_holdings) == len(holdings):
        return False
    save_holdings(next_holdings)
    return True


def import_from_csv(csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(csv_text.splitlines())
    if reader.fieldnames != CSV_COLUMNS:
        raise ValueError("CSV columns must be: symbol,shares,cost_basis,opened_at,notes")
    imported: list[dict[str, Any]] = []
    now = _now_iso()
    for row in reader:
        normalized = _normalize_create_payload(row)
        imported.append(
            {
                "id": str(uuid.uuid4()),
                **normalized,
                "created_at": now,
            }
        )
    if imported:
        save_holdings([*load_holdings(), *imported])
    return imported


def _bq_client_for_table(table: str):
    from google.cloud import bigquery

    project = table.split(".", 1)[0]
    return bigquery.Client(project=project)


def _bq_params(values: dict[str, Any]) -> list[Any]:
    from google.cloud import bigquery

    type_map = {
        "id": "STRING",
        "symbol": "STRING",
        "shares": "FLOAT64",
        "cost_basis": "FLOAT64",
        "opened_at": "DATE",
        "notes": "STRING",
    }
    params = []
    for key, value in values.items():
        try:
            param = bigquery.ScalarQueryParameter(key, type_map[key], value)
            getattr(param, "name")
            getattr(param, "value")
            params.append(param)
        except Exception:
            params.append(_QueryParam(key, value))
    return params


def _bq_job_config(values: dict[str, Any]):
    from google.cloud import bigquery

    params = _bq_params(values)
    config = bigquery.QueryJobConfig(query_parameters=params)
    try:
        if getattr(config, "query_parameters", None) is not params:
            config.query_parameters = params
    except Exception:
        pass
    return config


def _bq_row_to_holding(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "symbol": str(row.get("symbol") or "").upper(),
        "shares": float(row.get("shares") or 0.0),
        "cost_basis": float(row.get("cost_basis") or 0.0),
        "opened_at": _iso_value(row.get("opened_at")) or "",
        "notes": str(row.get("notes") or ""),
        "created_at": _iso_value(row.get("created_at")) or "",
        "updated_at": _iso_value(row.get("updated_at")) or None,
    }


def load_holdings_bigquery(table: str) -> list[dict[str, Any]]:
    client = _bq_client_for_table(table)
    sql = f"""
        SELECT id, symbol, shares, cost_basis, opened_at, notes, created_at, updated_at
        FROM `{table}`
        ORDER BY symbol ASC, created_at ASC
    """
    return [_bq_row_to_holding(dict(row)) for row in client.query(sql).result()]


def get_holding_bigquery(table: str, holding_id: str) -> dict[str, Any] | None:
    client = _bq_client_for_table(table)
    sql = f"""
        SELECT id, symbol, shares, cost_basis, opened_at, notes, created_at, updated_at
        FROM `{table}`
        WHERE id = @id
        LIMIT 1
    """
    rows = list(
        client.query(
            sql,
            job_config=_bq_job_config({"id": holding_id}),
        ).result()
    )
    return _bq_row_to_holding(dict(rows[0])) if rows else None


def add_holding_bigquery(table: str, data: dict[str, Any]) -> dict[str, Any]:
    holding = {
        "id": str(uuid.uuid4()),
        **_normalize_create_payload(data),
    }
    client = _bq_client_for_table(table)
    sql = f"""
        INSERT INTO `{table}` (id, symbol, shares, cost_basis, opened_at, notes, created_at, updated_at)
        VALUES (@id, @symbol, @shares, @cost_basis, @opened_at, @notes, CURRENT_TIMESTAMP(), NULL)
    """
    client.query(
        sql,
        job_config=_bq_job_config(holding),
    ).result()
    return get_holding_bigquery(table, holding["id"]) or {**holding, "created_at": _now_iso(), "updated_at": None}


def update_holding_bigquery(table: str, id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    holding_id = str(id or "").strip()
    if not holding_id:
        return None
    normalized_patch = _normalize_patch_payload(patch)
    if not normalized_patch:
        return get_holding_bigquery(table, holding_id)
    assignments = [f"{key} = @{key}" for key in normalized_patch]
    sql = f"""
        UPDATE `{table}`
        SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP()
        WHERE id = @id
    """
    params = {"id": holding_id, **normalized_patch}
    _bq_client_for_table(table).query(
        sql,
        job_config=_bq_job_config(params),
    ).result()
    return get_holding_bigquery(table, holding_id)


def delete_holding_bigquery(table: str, id: str) -> bool:
    holding_id = str(id or "").strip()
    if not holding_id or get_holding_bigquery(table, holding_id) is None:
        return False
    sql = f"DELETE FROM `{table}` WHERE id = @id"
    _bq_client_for_table(table).query(
        sql,
        job_config=_bq_job_config({"id": holding_id}),
    ).result()
    return True


def import_from_csv_bigquery(table: str, csv_text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(csv_text.splitlines())
    if reader.fieldnames != CSV_COLUMNS:
        raise ValueError("CSV columns must be: symbol,shares,cost_basis,opened_at,notes")
    imported = [add_holding_bigquery(table, dict(row)) for row in reader]
    return imported
