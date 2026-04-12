from war_room_stream import bump_war_room_stream_version, get_war_room_stream_version


def test_stream_version_bump():
    v0 = get_war_room_stream_version()
    bump_war_room_stream_version()
    assert get_war_room_stream_version() == v0 + 1
