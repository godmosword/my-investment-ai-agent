"""FastAPI backend for Q-Silicon Investment Report PWA.

Exposes daily metrics, trade recommendations, and report summaries
stored in BigQuery for consumption by the React PWA frontend.

Usage:
    uvicorn api:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.cloud import bigquery
from pydantic import BaseModel, Field, field_validator

import sse_token
from api_deps import get_bq_client as _bq_singleton
from api_routers import earnings as earnings_router
from api_routers import execution_intents as execution_intents_router
from api_routers import health as health_router
from api_routers import industries as industries_router
from api_routers import macro as macro_router
from api_routers import metrics as metrics_router
from api_routers import news as news_router
from api_routers import options as options_router
from api_routers import portfolio as portfolio_router
from api_routers import price_alerts as price_alerts_router
from api_routers import reports as reports_router
from api_routers import run_crew as run_crew_router
from api_routers import scenario as scenario_router
from api_routers import symbols as symbols_router
from api_routers import track_record as track_record_router
from api_routers import trades as trades_router
from api_routers.execution_intents import (
    _enrich_intents_with_gate_hints,
    _latest_gate_failure_summary,
)
from execution_intents import (
    intent_store_mtime,
    latest_execution_intents,
)
from paper_lifecycle import build_paper_lifecycle_payload
from symbol_snapshot_service import (
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)
from transparency_letter import build_transparency_letter
from war_room_stream import (
    drain_graph_node_events,
    drain_price_alert_events,
    get_war_room_stream_version,
)

logger = logging.getLogger(__name__)


def _get_bq_client() -> bigquery.Client:
    """BQ client accessor; tests monkeypatch ``api._get_bq_client``."""
    return _bq_singleton()


def run_paper_execution_tick(*args: Any, **kwargs: Any) -> Any:
    """Lazy proxy to ``paper_execution.run_paper_execution_tick``.

    Imported on first call so that FastAPI startup does not pull in the
    Job-side BigQuery writer. Tests still monkeypatch ``api.run_paper_execution_tick``.
    """
    from paper_execution import run_paper_execution_tick as _impl

    return _impl(*args, **kwargs)

# Prevent duplicate PAPER_* rows when two execution-tick requests arrive simultaneously
_paper_tick_lock = asyncio.Lock()



app = FastAPI(
    title="Q-Silicon Investment API",
    description="Daily crypto/AI investment report data API",
    version="1.0.0",
)

# Allow local dev (Vite), explicit production origins, and Vercel preview (*.vercel.app).
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://localhost:3000",
    ).split(",")
    if o.strip()
]
_CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(macro_router.router)
app.include_router(metrics_router.router)
app.include_router(news_router.router)
app.include_router(portfolio_router.router)
app.include_router(price_alerts_router.router)
app.include_router(run_crew_router.router)
app.include_router(scenario_router.router)
app.include_router(symbols_router.router)
app.include_router(track_record_router.router)
app.include_router(industries_router.router)
app.include_router(earnings_router.router)
app.include_router(execution_intents_router.router)
app.include_router(options_router.router)
app.include_router(reports_router.router)
app.include_router(trades_router.router)


def _qsilicon_master_key_required() -> str:
    """非空時，所有 ``/api/*``（除 SSE 專線）須 Header ``X-Q-Silicon-Key`` 與其完全一致。"""
    return (os.getenv("QSILICON_MASTER_KEY") or "").strip()


def _path_exempt_from_silicon_master_key(path: str) -> bool:
    """EventSource 無法自訂 Header；SSE 仍用 ``API_STREAM_AUTH_KEY``／query。"""
    return path == "/api/stream/war-room" or path.startswith("/api/stream/war-room/")


@app.middleware("http")
async def _qsilicon_master_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") or _path_exempt_from_silicon_master_key(path):
        return await call_next(request)
    master = _qsilicon_master_key_required()
    if not master:
        return await call_next(request)
    hdr = (request.headers.get("X-Q-Silicon-Key") or "").strip()
    if hdr != master:
        from starlette.responses import Response

        return Response(status_code=401, content="Unauthorized", media_type="text/plain")
    return await call_next(request)


@app.middleware("http")
async def _api_request_observability_middleware(request: Request, call_next):
    """Lightweight latency / outcome logging for Terminal-facing API routes (T1b)."""
    path = request.url.path
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if path.startswith("/api/"):
            logger.warning(
                "api_request path=%s method=%s status=exception elapsed_ms=%.1f",
                path,
                request.method,
                elapsed_ms,
            )
        raise
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if path.startswith("/api/") and os.getenv("API_HTTP_REQUEST_LOG", "0").lower() in (
        "1",
        "true",
        "yes",
    ):
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "api_request path=%s method=%s status=%s elapsed_ms=%.1f",
            path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
    return response




class WebPushSubscribeBody(BaseModel):
    """預留 Web Push 訂閱 payload（與 browser PushSubscription JSON 對齊）。"""

    endpoint: str = Field(..., max_length=4096)
    keys: dict[str, str] | None = None
    report_date: str | None = Field(default=None, max_length=32)
    block_id: str | None = Field(default=None, max_length=128)

    @field_validator("report_date")
    @classmethod
    def _validate_report_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        parts = s.split("-")
        if len(parts) != 3 or len(s) != 10:
            raise ValueError("report_date must be YYYY-MM-DD")
        y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        if not (2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
            raise ValueError("report_date out of range")
        return s

    @field_validator("block_id")
    @classmethod
    def _validate_block_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class WebPushTestSendBody(BaseModel):
    """管理端測試推送（須 ``WEB_PUSH_ADMIN_KEY`` 與 ``WEB_PUSH_VAPID_PRIVATE_KEY``）。"""

    title: str = Field(default="Q-Silicon", max_length=120)
    body: str = Field(default="Test notification", max_length=500)


class WarRoomSnapshot(BaseModel):
    gate_failure: dict[str, Any] | None = None
    scratchpad: dict[str, Any] | None = None
    execution_intents: list[dict[str, Any]] = Field(default_factory=list)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent




def _latest_scratchpad_summary() -> dict[str, Any] | None:
    scratchpad_dir = _repo_root() / ".qsilicon" / "scratchpad"
    if not scratchpad_dir.is_dir():
        return None
    files = sorted(scratchpad_dir.glob("*.jsonl"))
    if not files:
        return None
    latest = files[-1]
    try:
        lines = [
            json.loads(line)
            for line in latest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Could not read scratchpad %s: %s", latest, exc)
        return None
    if not lines:
        return {"path": str(latest), "events": []}
    init_event = next((line for line in lines if line.get("type") == "init"), None)
    gate_events = [line for line in lines if line.get("type") == "gate_result"]
    final_event = next((line for line in reversed(lines) if line.get("type") == "run_end"), None)
    return {
        "path": str(latest),
        "run_id": lines[0].get("runId"),
        "event_count": len(lines),
        "init_meta": (init_event or {}).get("meta", {}),
        "latest_gate_result": gate_events[-1] if gate_events else None,
        "final_status": (final_event or {}).get("status"),
        "final_event": final_event,
    }


def _sse_auth_ok(request: Request) -> bool:
    key = (os.getenv("API_STREAM_AUTH_KEY") or "").strip()
    if not key:
        return True
    if request.headers.get("X-QS-Stream-Key") == key or request.query_params.get("stream_key") == key:
        return True
    token = request.headers.get("X-QS-Stream-Token") or request.query_params.get("stream_token")
    return sse_token.verify(token)


def _sse_mint_auth_ok(request: Request) -> bool:
    """Minting a short-lived SSE token requires the long-lived key (header or query)."""
    key = (os.getenv("API_STREAM_AUTH_KEY") or "").strip()
    if not key:
        return False
    return (
        request.headers.get("X-QS-Stream-Key") == key
        or request.query_params.get("stream_key") == key
    )


@app.post("/api/stream/token")
def post_stream_token(request: Request) -> dict[str, Any]:
    """Mint a short-lived token for SSE auth (Phase 3 backlog closure).

    404 unless ``API_STREAM_AUTH_KEY`` is set; the caller must present that key
    via ``X-QS-Stream-Key`` header (preferred) or ``stream_key`` query parameter.
    TTL is bounded by ``SSE_TOKEN_TTL_SECONDS`` (default 60s, clamped 10–600s).
    """
    if not (os.getenv("API_STREAM_AUTH_KEY") or "").strip():
        raise HTTPException(status_code=404, detail="stream tokens disabled; set API_STREAM_AUTH_KEY")
    if not _sse_mint_auth_ok(request):
        raise HTTPException(status_code=403, detail="invalid or missing stream auth key")
    minted = sse_token.mint()
    return {
        "token": minted.token,
        "expires_at": minted.expires_at,
        "ttl_seconds": minted.ttl_seconds,
    }


def _paper_tick_auth_ok(request: Request) -> bool:
    key = (os.getenv("PAPER_TICK_API_KEY") or "").strip()
    if not key:
        return True
    return request.headers.get("X-Paper-Tick-Key") == key


def _web_push_admin_ok(request: Request) -> bool:
    key = (os.getenv("WEB_PUSH_ADMIN_KEY") or "").strip()
    if not key:
        return False
    return request.headers.get("X-Web-Push-Admin-Key") == key


def _parse_sse_watch_symbols_param(raw: str | None, max_n: int = 8) -> list[str]:
    """Parse ``watch_symbols=BTC,NVDA`` for war-room SSE ``symbol_quote`` events."""
    if not raw or not str(raw).strip():
        return []
    out: list[str] = []
    for part in str(raw).split(","):
        if len(out) >= max_n:
            break
        piece = part.strip()
        if not piece:
            continue
        try:
            out.append(validate_symbol_for_snapshot(piece))
        except ValueError:
            continue
    return out


@app.get("/api/paper/lifecycle")
def get_paper_lifecycle(
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    """Paper lifecycle summary from execution_intents.jsonl; read-only, no quote calls."""
    return build_paper_lifecycle_payload(limit=limit, status=status, category=category)


@app.get("/api/paper/pnl")
def get_paper_pnl(
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    """Paper realized/unrealized P&L with best-effort quotes for active rows."""
    return build_paper_lifecycle_payload(
        limit=limit,
        status=status,
        category=category,
        quote_fn=fetch_symbol_quote,
        include_quotes=True,
    )


@app.get("/api/paper/transparency-letter")
def get_paper_transparency_letter(
    month: str | None = Query(default=None, description="Optional month in YYYY-MM format."),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    """Internal monthly paper transparency letter; never publishes externally."""
    try:
        return build_transparency_letter(month=month, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/push/subscribe")
def push_subscribe(request: Request, body: WebPushSubscribeBody) -> dict[str, Any]:
    """Web Push 訂閱：預設關閉；開啟後見 ``web_push_store``（Redis／程序內／log-only）。"""
    import web_push_store

    if not web_push_store.web_push_enabled():
        raise HTTPException(
            status_code=501,
            detail=(
                "Web Push 未啟用。設 WEB_PUSH_ENABLED=1 後可 POST 訂閱；"
                "可選 WEB_PUSH_STORE=1 啟用程序內暫存（非持久化）。詳見 docs/PWA_WEB_PUSH.md。"
            ),
        )
    client_ip = (request.client.host if request.client else "") or ""
    meta = web_push_store.record_subscription(body.model_dump(mode="json"), client_ip=client_ip)
    return {"ok": True, **meta}


@app.post("/api/push/test-send")
def push_test_send(request: Request, body: WebPushTestSendBody) -> dict[str, Any]:
    """對已存訂閱送一則 **測試** Web Push（``pywebpush``）。須 ``WEB_PUSH_ADMIN_KEY`` Header。"""
    import web_push_store

    if not web_push_store.web_push_enabled():
        raise HTTPException(status_code=501, detail="Web Push disabled")
    if not _web_push_admin_ok(request):
        raise HTTPException(status_code=404, detail="admin endpoint disabled or invalid key")
    return web_push_store.send_test_push(body.title, body.body)


@app.get("/api/war-room/latest")
def get_war_room_latest() -> dict[str, Any]:
    """Read-only War Room snapshot from local gate-failure artifacts and scratchpad."""
    gate = _latest_gate_failure_summary()
    intents = latest_execution_intents(limit=20)
    payload = WarRoomSnapshot(
        gate_failure=gate,
        scratchpad=_latest_scratchpad_summary(),
        execution_intents=_enrich_intents_with_gate_hints(intents, gate),
    )
    return payload.model_dump(mode="json")


def _war_room_fingerprint() -> dict[str, Any]:
    return {
        "stream_version": get_war_room_stream_version(),
        "intent_store_mtime": intent_store_mtime(),
    }


@app.get("/api/stream/war-room")
async def stream_war_room(
    request: Request,
    watch_symbols: str | None = Query(
        default=None,
        description="Comma-separated symbols (max 8) for ``symbol_quote`` SSE events.",
    ),
):
    """SSE: war-room snapshot + optional per-symbol quotes (queue 29). Disabled unless ``TERMINAL_SSE_ENABLED=1``."""
    if os.getenv("TERMINAL_SSE_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="SSE disabled; set TERMINAL_SSE_ENABLED=1")
    if not _sse_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing stream auth")

    interval = float(os.getenv("TERMINAL_SSE_POLL_SEC", "2") or "2")
    interval = max(0.5, min(interval, 30.0))

    # Explicit per-connection event-rate cap (Phase 3 backlog closure).
    # 0 / unset = disabled. Counted across node_complete / price_alert /
    # war_room_update / symbol_quote yields; keepalive comments are exempt.
    try:
        max_eps = float(os.getenv("SSE_MAX_EVENTS_PER_SEC", "0") or "0")
    except (TypeError, ValueError):
        max_eps = 0.0
    max_eps = max(0.0, min(max_eps, 100.0))

    async def event_gen():
        last_fp: dict[str, Any] | None = None
        last_quote_sigs: dict[str, str] = {}
        window_start = time.time()
        window_count = 0
        throttled_in_window = False

        def _allow_event() -> bool:
            nonlocal window_start, window_count, throttled_in_window
            if max_eps <= 0:
                return True
            now = time.time()
            if now - window_start >= 1.0:
                window_start = now
                window_count = 0
                throttled_in_window = False
            if window_count < max_eps:
                window_count += 1
                return True
            return False

        while True:
            if await request.is_disconnected():
                break

            # Drain per-node events first — these are granular state transitions.
            node_events = drain_graph_node_events()
            for event in node_events:
                if not _allow_event():
                    if not throttled_in_window:
                        throttled_in_window = True
                        warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                        yield f"event: throttled\ndata: {warn}\n\n"
                    break
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: node_complete\ndata: {payload}\n\n"

            # Drain price-alert events (M4 slice 3): triggered alerts → PWA toast.
            alert_events = drain_price_alert_events()
            for event in alert_events:
                if not _allow_event():
                    if not throttled_in_window:
                        throttled_in_window = True
                        warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                        yield f"event: throttled\ndata: {warn}\n\n"
                    break
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: price_alert\ndata: {payload}\n\n"

            # Full war-room snapshot when fingerprint changes.
            fp = _war_room_fingerprint()
            if fp != last_fp and _allow_event():
                last_fp = fp
                body = get_war_room_latest()
                payload = json.dumps(body, ensure_ascii=False)
                yield f"event: war_room_update\ndata: {payload}\n\n"

            watch_list = _parse_sse_watch_symbols_param(watch_symbols or request.query_params.get("watch_symbols"))
            for sym in watch_list:
                raw = fetch_symbol_quote(sym)
                quote_obj = {
                    "symbol": raw.get("symbol"),
                    "last": raw.get("last"),
                    "as_of": str(raw.get("as_of") or ""),
                    "change_pct_1d": raw.get("change_pct_1d"),
                    "currency": raw.get("currency"),
                    "error": raw.get("error"),
                    "cached": raw.get("cached"),
                }
                sig = json.dumps(quote_obj, ensure_ascii=False, sort_keys=True)
                if last_quote_sigs.get(sym) != sig:
                    if not _allow_event():
                        if not throttled_in_window:
                            throttled_in_window = True
                            warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                            yield f"event: throttled\ndata: {warn}\n\n"
                        break
                    last_quote_sigs[sym] = sig
                    envelope = {"type": "symbol_quote", "symbol": sym, "quote": quote_obj}
                    yield f"event: symbol_quote\ndata: {json.dumps(envelope, ensure_ascii=False)}\n\n"

            yield ": keepalive\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/paper/execution-tick")
async def post_paper_execution_tick(request: Request) -> dict[str, Any]:
    """Run one paper simulation pass (M5). Disabled unless ``PAPER_TICK_HTTP_ENABLED=1``."""
    if os.getenv("PAPER_TICK_HTTP_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="paper tick HTTP disabled")
    if not _paper_tick_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing paper tick auth")
    if _paper_tick_lock.locked():
        raise HTTPException(status_code=409, detail="paper tick already in progress")
    async with _paper_tick_lock:
        written = run_paper_execution_tick()
    return {"ok": True, "written": len(written), "rows": written}
