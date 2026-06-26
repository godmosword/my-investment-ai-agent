from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import app
from api_routers import news


class FakeDoc:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data
        self.exists = True

    def to_dict(self) -> dict:
        return dict(self._data)


class FakeMissingDoc:
    exists = False


class FakeQuery:
    def __init__(self, docs: list[FakeDoc]):
        self._docs = list(docs)

    def where(self, field: str, _op: str, value: str) -> "FakeQuery":
        return FakeQuery(
            [
                doc
                for doc in self._docs
                if str(doc.to_dict().get(field) or "").startswith(value)
                or str(doc.to_dict().get("published_at") or "").startswith(value)
            ]
        )

    def order_by(self, field: str, direction: str | None = None) -> "FakeQuery":
        reverse = str(direction or "").upper() == "DESCENDING"
        return FakeQuery(
            sorted(
                self._docs,
                key=lambda doc: str(doc.to_dict().get(field) or ""),
                reverse=reverse,
            )
        )

    def limit(self, limit: int) -> "FakeQuery":
        return FakeQuery(self._docs[:limit])

    def stream(self) -> list[FakeDoc]:
        return list(self._docs)


class FakeCollection(FakeQuery):
    def document(self, doc_id: str):
        for doc in self._docs:
            if doc.id == doc_id:
                return FakeDocumentRef(doc)
        return FakeDocumentRef(FakeMissingDoc())


class FakeDocumentRef:
    def __init__(self, doc):
        self._doc = doc

    def get(self):
        return self._doc


class FakeClient:
    def __init__(self, docs: list[FakeDoc]):
        self._docs = docs

    def collection(self, _name: str) -> FakeCollection:
        return FakeCollection(self._docs)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("TECH_PULSE_FIRESTORE_COLLECTION", "tech_pulse_memory_items")
    docs = [
        FakeDoc(
            "ai-chip",
            {
                "headline": "AI 半導體供應鏈拉高資本支出",
                "gemini_take": "雲端 capex 仍是先進封裝與 HBM 的核心推力。",
                "source_url": "https://semianalysis.com/mock-ai-chip",
                "published_at": "2026-05-13T09:30:00Z",
                "tags": ["AI", "半導體"],
                "confidence": 0.82,
                "deep_brief": "供應鏈的瓶頸仍集中在先進封裝。",
                "thesis_breakdown": ["HBM 需求偏強", "先進封裝排程仍緊"],
                "tickers": ["NVDA", "TSM"],
            },
        ),
        FakeDoc(
            "macro-dollar",
            {
                "title": "美元回落支撐風險資產",
                "summary": "DXY 下滑改善高 beta 科技股估值壓力。",
                "source_domain": "bloomberg.com",
                "published_at": "2026-05-13T08:00:00Z",
                "tags": ["宏觀"],
                "confidence_score": "0.64",
            },
        ),
        FakeDoc(
            "crypto-etf",
            {
                "headline": "Bitcoin ETF 資金流回溫",
                "gemini_take": "加密資產風險偏好改善，但仍需觀察美元與實質利率。",
                "source_url": "https://cointelegraph.com/mock-bitcoin-etf",
                "published_at": "2026-05-13T10:00:00Z",
                "tags": ["Crypto", "BTC"],
                "pillar": "crypto",
                "confidence": 0.71,
                "content": "Bitcoin ETF 資金流回溫，使 BTC 現貨買盤重新成為風險偏好的觀察窗口。",
                "tickers": ["BTC"],
            },
        ),
        FakeDoc(
            "unsourced",
            {
                "headline": "沒有來源的新聞不得出現",
                "gemini_take": "這筆資料應被 API 過濾。",
                "published_at": "2026-05-13T07:00:00Z",
                "tags": ["AI"],
                "deep_brief": "沒有來源的 deep brief 不得出現。",
            },
        ),
    ]
    news._firestore_client = FakeClient(docs)
    yield TestClient(app)
    news._firestore_client = None


def test_news_digest_filters_unsourced_items(client):
    response = client.get("/api/news/digest?date=2026-05-13&limit=10")
    assert response.status_code == 200
    body = response.json()
    headlines = [item["headline"] for item in body["items"]]
    assert "AI 半導體供應鏈拉高資本支出" in headlines
    assert "美元回落支撐風險資產" in headlines
    assert "沒有來源的新聞不得出現" not in headlines
    assert all(item["source_domain"] for item in body["items"])
    assert all(item["freshness"] in {"fresh", "stale", "unknown"} for item in body["items"])
    assert {theme["label"] for theme in body["themes"]} >= {"AI", "半導體", "宏觀"}


def test_news_normalization_surfaces_freshness_and_missing_fields():
    fresh = news._normalize_item(
        {
            "headline": "Fresh AI brief",
            "gemini_take": "Fresh take",
            "source_url": "https://example.com/fresh",
            "published_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        },
        "fresh",
    )
    assert fresh is not None
    assert fresh["freshness"] == "fresh"
    assert fresh["missing_fields"] == []

    incomplete = news._normalize_item(
        {
            "headline": "Missing published timestamp",
            "gemini_take": "Still usable, but quality metadata should say what is missing.",
            "source_domain": "example.com",
        },
        "missing",
    )
    assert incomplete is not None
    assert incomplete["freshness"] == "unknown"
    assert set(incomplete["missing_fields"]) == {"published_at", "source_url"}


def test_news_deep_returns_thesis_and_confidence(client):
    response = client.get("/api/news/deep/ai-chip")
    assert response.status_code == 200
    body = response.json()
    assert body["headline"] == "AI 半導體供應鏈拉高資本支出"
    assert body["source_domain"] == "semianalysis.com"
    assert body["confidence"] == pytest.approx(0.82)
    assert body["thesis_breakdown"] == ["HBM 需求偏強", "先進封裝排程仍緊"]
    assert body["tickers"] == ["NVDA", "TSM"]
    assert body["title"] == body["headline"]
    assert body["body"] == body["deep_brief"]
    assert body["reading_minutes"] >= 1


def test_news_deep_list_filters_by_pillar_and_skips_unsourced(client):
    response = client.get("/api/news/deep?pillar=semiconductor&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["pillar"] == "semiconductor"
    ids = [item["id"] for item in body["items"]]
    assert ids == ["ai-chip"]
    item = body["items"][0]
    assert item["source_domain"] == "semianalysis.com"
    assert item["title"] == "AI 半導體供應鏈拉高資本支出"
    assert item["summary"] == "雲端 capex 仍是先進封裝與 HBM 的核心推力。"
    assert item["body"] == "供應鏈的瓶頸仍集中在先進封裝。"
    assert item["reading_minutes"] >= 1
    assert "unsourced" not in ids


def test_news_deep_list_accepts_crypto_aliases(client):
    response = client.get("/api/news/deep?pillar=BTC&limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["pillar"] == "crypto"
    assert [item["id"] for item in body["items"]] == ["crypto-etf"]


def test_news_deep_list_rejects_unknown_pillar(client):
    response = client.get("/api/news/deep?pillar=macro")
    assert response.status_code == 422


def test_news_themes_counts_tags(client):
    response = client.get("/api/news/themes")
    assert response.status_code == 200
    themes = {row["label"]: row["count"] for row in response.json()["themes"]}
    assert themes["AI"] == 1
    assert themes["半導體"] == 1
    assert themes["宏觀"] == 1


def test_news_digest_returns_503_when_firestore_unavailable(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setattr(news, "_get_firestore_client", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    response = TestClient(app).get("/api/news/digest")
    assert response.status_code == 503
