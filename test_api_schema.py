"""Tests for api_schema.py helpers."""

import pytest

from api_schema import log_schema_mismatch, require_json_dict, require_json_list, require_list


@pytest.mark.smoke
class TestRequireJsonDict:
    def test_returns_dict_unchanged(self):
        d = {"key": "value", "count": 3}
        assert require_json_dict(d, source="Test") is d

    def test_raises_on_list(self):
        with pytest.raises(ValueError, match="CoinGlass"):
            require_json_dict([1, 2, 3], source="CoinGlass")

    def test_raises_on_none(self):
        with pytest.raises(ValueError):
            require_json_dict(None)

    def test_raises_on_string(self):
        with pytest.raises(ValueError, match="dict"):
            require_json_dict("oops", source="NewsAPI")

    def test_no_source_still_raises(self):
        with pytest.raises(ValueError):
            require_json_dict(42)


@pytest.mark.smoke
class TestRequireJsonList:
    def test_returns_list_unchanged(self):
        lst = [1, {"a": 2}]
        assert require_json_list(lst, source="Binance") is lst

    def test_raises_on_dict(self):
        with pytest.raises(ValueError, match="FMP"):
            require_json_list({"x": 1}, source="FMP")

    def test_raises_on_none(self):
        with pytest.raises(ValueError):
            require_json_list(None, source="API")


@pytest.mark.smoke
class TestRequireList:
    def test_top_level_key(self):
        obj = {"results": [1, 2, 3]}
        assert require_list(obj, "results", source="Test") == [1, 2, 3]

    def test_nested_path(self):
        obj = {"data": {"items": ["a", "b"]}}
        assert require_list(obj, "data.items", source="CoinGlass") == ["a", "b"]

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="missing key"):
            require_list({"a": 1}, "results", source="NewsAPI")

    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            require_list({"items": {"nested": "dict"}}, "items", source="API")

    def test_non_dict_at_intermediate_raises(self):
        with pytest.raises(ValueError, match="dict at"):
            require_list({"data": "string_not_dict"}, "data.items", source="API")

    def test_empty_list_is_valid(self):
        obj = {"results": []}
        assert require_list(obj, "results") == []


@pytest.mark.smoke
class TestLogSchemaMismatch:
    def test_does_not_raise(self):
        """log_schema_mismatch should only log, never raise."""
        log_schema_mismatch("CoinGlass", expected="dict", got=[1, 2, 3])
        log_schema_mismatch("", expected="list", got=None)
        log_schema_mismatch("API", expected="key 'results'", got={"other": 1})

    def test_long_repr_is_truncated(self, caplog):
        """Very long got values should be truncated in the log message."""
        import logging
        huge_list = list(range(1000))
        with caplog.at_level(logging.WARNING):
            log_schema_mismatch("BigAPI", expected="str", got=huge_list)
        # The log record should exist and contain a truncated repr
        records = [r for r in caplog.records if "BigAPI" in r.message]
        assert records, "Expected a log record mentioning BigAPI"
        assert len(records[0].message) < 500, "Log message should be reasonably short"
