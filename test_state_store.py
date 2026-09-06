"""state_store：repo-backed append-only JSONL 狀態層的契約測試。

GCP 移除後，BigQuery 表被本地 JSONL 取代；這裡固定該層的讀寫語意，
避免日後 backend 切換時靜默改變行為。
"""

from __future__ import annotations

import json

import pytest

import state_store


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path, monkeypatch):
    """每個測試各自一個 state dir，避免污染 repo 內的 .qsilicon/。"""
    monkeypatch.setenv("QSILICON_STATE_DIR", str(tmp_path / "state"))
    yield


def test_read_missing_store_returns_empty_list():
    assert state_store.read_jsonl("nope.jsonl") == []


def test_append_then_read_round_trip():
    rows = [{"a": 1}, {"a": 2}]
    written = state_store.append_jsonl("t.jsonl", rows)
    assert written == 2
    assert state_store.read_jsonl("t.jsonl") == rows


def test_append_is_additive_not_overwriting():
    state_store.append_jsonl("t.jsonl", [{"a": 1}])
    state_store.append_jsonl("t.jsonl", [{"a": 2}])
    assert state_store.read_jsonl("t.jsonl") == [{"a": 1}, {"a": 2}]


def test_append_empty_rows_is_noop():
    assert state_store.append_jsonl("t.jsonl", []) == 0
    assert not state_store.store_path("t.jsonl").exists()


def test_replace_truncates_previous_content():
    state_store.append_jsonl("t.jsonl", [{"a": 1}, {"a": 2}])
    state_store.replace_jsonl("t.jsonl", [{"a": 3}])
    assert state_store.read_jsonl("t.jsonl") == [{"a": 3}]


def test_replace_with_empty_rows_clears_store():
    state_store.append_jsonl("t.jsonl", [{"a": 1}])
    state_store.replace_jsonl("t.jsonl", [])
    assert state_store.read_jsonl("t.jsonl") == []


def test_corrupt_line_is_skipped_not_fatal():
    """半寫入的行（runner 被砍）不得讓整個讀取路徑爆掉。"""
    path = state_store.store_path("t.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1}\n{"a": broken\n{"a": 3}\n', encoding="utf-8")
    assert state_store.read_jsonl("t.jsonl") == [{"a": 1}, {"a": 3}]


def test_non_ascii_is_written_unescaped():
    state_store.append_jsonl("t.jsonl", [{"note": "台北"}])
    raw = state_store.store_path("t.jsonl").read_text(encoding="utf-8")
    assert "台北" in raw
    assert state_store.read_jsonl("t.jsonl") == [{"note": "台北"}]


def test_read_applies_limit_to_tail():
    state_store.append_jsonl("t.jsonl", [{"a": i} for i in range(5)])
    assert state_store.read_jsonl("t.jsonl", limit=2) == [{"a": 3}, {"a": 4}]


def test_store_path_honours_state_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("QSILICON_STATE_DIR", str(tmp_path / "elsewhere"))
    assert state_store.store_path("t.jsonl") == tmp_path / "elsewhere" / "t.jsonl"


def test_store_path_rejects_escaping_the_state_dir():
    with pytest.raises(ValueError):
        state_store.store_path("../outside.jsonl")


def test_rows_must_be_json_serialisable():
    with pytest.raises(TypeError):
        state_store.append_jsonl("t.jsonl", [{"bad": object()}])


def test_failed_append_leaves_store_unchanged():
    """序列化失敗時不得留下半截檔案。"""
    state_store.append_jsonl("t.jsonl", [{"a": 1}])
    with pytest.raises(TypeError):
        state_store.append_jsonl("t.jsonl", [{"a": 2}, {"bad": object()}])
    assert state_store.read_jsonl("t.jsonl") == [{"a": 1}]


def test_append_writes_one_json_object_per_line():
    state_store.append_jsonl("t.jsonl", [{"a": 1}, {"a": 2}])
    lines = state_store.store_path("t.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"a": 2}]
