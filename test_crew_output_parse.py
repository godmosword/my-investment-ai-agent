"""Tests for Crew kickoff JSON extraction (LLM-invalid JSON tolerances)."""

import json

import pytest
from pydantic import BaseModel, ValidationError

from crew_output_parse import (
    kickoff_to_pydantic,
    kickoff_with_structured_fallback,
    parse_pydantic_from_llm_json_text,
    repair_llm_json_text,
)


class _Tiny(BaseModel):
    a: int
    b: list[int]


def test_repair_llm_json_text_strips_trailing_commas() -> None:
    bad = '{"a": 1, "b": [2, 3,],}'
    fixed = repair_llm_json_text(bad)
    assert json.loads(fixed) == {"a": 1, "b": [2, 3]}


def test_repair_llm_json_text_nested_trailing_commas() -> None:
    bad = '{"a": {"x": 1,}, "b": [],}'
    fixed = repair_llm_json_text(bad)
    assert json.loads(fixed) == {"a": {"x": 1}, "b": []}


def test_kickoff_to_pydantic_parses_raw_with_trailing_comma() -> None:
    class R:
        tasks_output = [
            type(
                "TaskOut",
                (),
                {"pydantic": None, "raw": '{"a": 7, "b": [1, 2,],}', "summary": None},
            )()
        ]

    obj = kickoff_to_pydantic(R(), _Tiny)
    assert obj.a == 7
    assert obj.b == [1, 2]


def test_parse_pydantic_from_llm_json_text_trailing_comma() -> None:
    obj = parse_pydantic_from_llm_json_text('{"a": 7, "b": [1, 2,],}', _Tiny)
    assert obj.a == 7
    assert obj.b == [1, 2]


def test_kickoff_with_structured_fallback_recovers_from_validation_error() -> None:
    class _Crew:
        def kickoff(self, **kwargs: object) -> None:  # noqa: ARG002
            try:
                _Tiny.model_validate_json('{"a": 1, "b": [],}')
            except ValidationError as e:
                raise e

    section = kickoff_with_structured_fallback(_Crew(), _Tiny, inputs={})
    assert section.a == 1
    assert section.b == []


def test_kickoff_with_structured_fallback_reraises_when_unrecoverable() -> None:
    class _Crew:
        def kickoff(self, **kwargs: object) -> None:  # noqa: ARG002
            raise RuntimeError("no json here")

    with pytest.raises(RuntimeError, match="no json here"):
        kickoff_with_structured_fallback(_Crew(), _Tiny, inputs={})


def test_kickoff_with_structured_fallback_success_uses_kickoff_to_pydantic() -> None:
    class R:
        tasks_output = [
            type(
                "TaskOut",
                (),
                {"pydantic": None, "raw": '{"a": 3, "b": [1,],}', "summary": None},
            )()
        ]

    class _Crew:
        def kickoff(self, **kwargs: object) -> object:  # noqa: ARG002
            return R()

    section = kickoff_with_structured_fallback(_Crew(), _Tiny, inputs={})
    assert section.a == 3
    assert section.b == [1]
