"""Extract Pydantic models from CrewAI kickoff results with JSON fallbacks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# RFC 8259 JSON forbids trailing commas; LLMs often emit `{"a":1,}` or `[1,2,]`.
_TRAILING_COMMA_BEFORE_CLOSE = re.compile(r",(\s*[\]}])")


def repair_llm_json_text(s: str) -> str:
    """Best-effort normalization so strict JSON parsers accept common LLM mistakes."""
    text = s.strip()
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_COMMA_BEFORE_CLOSE.sub(r"\1", text)
    return text


def _strip_markdown_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = _FENCE_RE.sub("", s)
    return s.strip()


def parse_pydantic_from_llm_json_text(raw_text: str, model_cls: type[T]) -> T:
    """Strip fences, repair trailing commas, then validate as ``model_cls``."""
    cleaned = repair_llm_json_text(_strip_markdown_fences(raw_text))
    try:
        return model_cls.model_validate_json(cleaned)
    except Exception as e1:
        logger.warning("model_validate_json failed (%s), trying json.loads: %s", model_cls.__name__, e1)
    try:
        data = json.loads(cleaned)
        return model_cls.model_validate(data)
    except Exception as e2:
        logger.error("Structured parse failed for %s: %s", model_cls.__name__, e2)
        raise


def _extract_json_invalid_string(exc: BaseException) -> str | None:
    """Walk ``__cause__`` / ``__context__`` and return first ``json_invalid`` input string."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        e = stack.pop()
        eid = id(e)
        if eid in seen:
            continue
        seen.add(eid)
        if isinstance(e, ValidationError):
            for item in e.errors():
                if item.get("type") == "json_invalid":
                    val = item.get("input")
                    if isinstance(val, str) and val.strip():
                        return val
        if e.__cause__ is not None:
            stack.append(e.__cause__)
        ctx = e.__context__
        if ctx is not None and ctx is not e.__cause__:
            stack.append(ctx)
    return None


def _try_recover_model_from_exception_chain(exc: BaseException, model_cls: type[T]) -> T | None:
    raw = _extract_json_invalid_string(exc)
    if raw is None:
        return None
    try:
        return parse_pydantic_from_llm_json_text(raw, model_cls)
    except Exception as e2:
        logger.warning("kickoff failure JSON repair did not yield %s: %s", model_cls.__name__, e2)
        return None


def kickoff_with_structured_fallback(
    crew: Any,
    model_cls: type[T],
    *,
    inputs: dict[str, Any] | None = None,
    input_files: Any | None = None,
) -> T:
    """
    Run ``crew.kickoff`` then ``kickoff_to_pydantic``.

    If kickoff raises (e.g. CrewAI converts bad JSON with ``output_pydantic`` into
    ``ValidationError`` before returning), walk the exception chain for Pydantic
    ``json_invalid`` payload and retry with the same repair path as
    ``kickoff_to_pydantic``.
    """
    kw: dict[str, Any] = {}
    if inputs is not None:
        kw["inputs"] = inputs
    if input_files is not None:
        kw["input_files"] = input_files
    try:
        result = crew.kickoff(**kw)
    except ValidationError as e:
        recovered = _try_recover_model_from_exception_chain(e, model_cls)
        if recovered is not None:
            logger.warning(
                "crew.kickoff raised ValidationError; recovered %s via JSON repair",
                model_cls.__name__,
            )
            return recovered
        raise
    except Exception as e:
        recovered = _try_recover_model_from_exception_chain(e, model_cls)
        if recovered is not None:
            logger.warning(
                "crew.kickoff raised %s; recovered %s via nested json_invalid repair",
                type(e).__name__,
                model_cls.__name__,
            )
            return recovered
        raise

    return kickoff_to_pydantic(result, model_cls)


def kickoff_to_pydantic(result: Any, model_cls: type[T]) -> T:
    """
    Prefer TaskOutput.pydantic from the final task; else parse raw JSON from last task.
    """
    pyd: Any = None
    raw_text: str | None = None

    tasks_out = getattr(result, "tasks_output", None) or []
    if tasks_out:
        last = tasks_out[-1]
        pyd = getattr(last, "pydantic", None)
        raw_text = getattr(last, "raw", None) or getattr(last, "summary", None)

    if pyd is None:
        pyd = getattr(result, "pydantic", None)

    if isinstance(pyd, model_cls):
        return pyd
    if isinstance(pyd, BaseModel):
        try:
            return model_cls.model_validate(pyd.model_dump())
        except Exception as e:
            logger.warning("Coerce BaseModel → %s failed: %s", model_cls.__name__, e)

    if raw_text is None:
        raw_text = str(result)

    return parse_pydantic_from_llm_json_text(raw_text, model_cls)
