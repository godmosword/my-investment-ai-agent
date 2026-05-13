from war_room_stream import (
    bump_war_room_stream_version,
    drain_graph_node_events,
    emit_graph_node_event,
    get_war_room_stream_version,
)


def test_stream_version_bump():
    v0 = get_war_room_stream_version()
    bump_war_room_stream_version()
    assert get_war_room_stream_version() == v0 + 1


def test_graph_node_events_drain_fifo_and_bump_version():
    drain_graph_node_events(max_items=1000)
    v0 = get_war_room_stream_version()

    emit_graph_node_event("trade_picker", {"intent_count": 2})
    emit_graph_node_event("market_gate", {"allowed": 1, "blocked": 1}, phase="begin", summary="g", run_id="r1")

    assert get_war_room_stream_version() == v0 + 2
    first = drain_graph_node_events(max_items=1)
    second = drain_graph_node_events()

    assert [event["node"] for event in first] == ["trade_picker"]
    assert [event["node"] for event in second] == ["market_gate"]
    assert second[0]["allowed"] == 1
    assert first[0]["v"] == 1
    assert first[0]["kind"] == "graph_node"
    assert first[0]["phase"] == "end"
    assert first[0]["payload"]["intent_count"] == 2
    assert first[0]["intent_count"] == 2
    assert second[0]["phase"] == "begin"
    assert second[0]["summary"] == "g"
    assert second[0]["run_id"] == "r1"
