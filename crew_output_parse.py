"""Extract Pydantic models from CrewAI kickoff results with JSON fallbacks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_markdown_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = _FENCE_RE.sub("", s)
    return s.strip()


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

    cleaned = _strip_markdown_fences(raw_text)
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
