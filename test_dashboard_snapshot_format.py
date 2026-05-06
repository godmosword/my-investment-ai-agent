from dashboard.snapshot_format import format_price_alignment_status, format_provenance_summary


def test_price_alignment_status_matches_terminal_labels():
    assert format_price_alignment_status(None).startswith("對齊狀態：N/A")
    assert format_price_alignment_status({"aligned": True}).startswith("對齊狀態：一致")
    assert "OHLC 與 quote 不一致" in format_price_alignment_status(
        {"aligned": False, "rel_diff": 0.00123}
    )
    assert "quote down" in format_price_alignment_status({"quote_error": "quote down"})


def test_provenance_summary_formats_shared_sources():
    text = format_provenance_summary(
        {
            "ohlc": {"source": "yfinance", "as_of": "2026-05-06T00:00:00Z"},
            "daily_metrics": {
                "source": "bigquery",
                "as_of": "2026-05-06T01:00:00Z",
                "table_id": "p.d.t",
            },
        }
    )
    assert "OHLC: yfinance" in text
    assert "daily_metrics: bigquery" in text
    assert "p.d.t" in text
