"""Contract tests for tools_cache_http: JSON parsing and HTTP error paths."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest
import requests

from tools_cache_http import _http_get, _response_json_dict, _response_json_list

pytestmark = pytest.mark.boundary


class TestResponseJsonParsing(unittest.TestCase):
    def test_dict_happy_path(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {"ok": True, "data": 1}
        out = _response_json_dict(resp, source="test")
        self.assertEqual(out, {"ok": True, "data": 1})

    def test_dict_non_json_body_returns_none(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.json.side_effect = ValueError("not json")
        self.assertIsNone(_response_json_dict(resp, source="test"))

    def test_dict_json_list_returns_none(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = [{"a": 1}]
        self.assertIsNone(_response_json_dict(resp, source="test"))

    def test_list_happy_path(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = [1, 2, 3]
        out = _response_json_list(resp, source="test")
        self.assertEqual(out, [1, 2, 3])

    def test_list_dict_body_returns_none(self) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {"not": "a list"}
        self.assertIsNone(_response_json_list(resp, source="test"))


class TestHttpGetErrors(unittest.TestCase):
    @patch("tools_cache_http._get_http_session")
    def test_timeout_raises(self, mock_sess: MagicMock) -> None:
        mock_sess.return_value.get.side_effect = requests.exceptions.Timeout("boom")
        with self.assertRaises(requests.exceptions.Timeout):
            _http_get("https://example.invalid/test", timeout=0.001)

    @patch("tools_cache_http._get_http_session")
    def test_connection_error_raises(self, mock_sess: MagicMock) -> None:
        mock_sess.return_value.get.side_effect = requests.exceptions.ConnectionError("nxdomain")
        with self.assertRaises(requests.exceptions.ConnectionError):
            _http_get("https://example.invalid/test")

    @patch("tools_cache_http._get_http_session")
    def test_429_returns_response(self, mock_sess: MagicMock) -> None:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 429
        mock_sess.return_value.get.return_value = resp
        self.assertIs(_http_get("https://example.invalid/r"), resp)
