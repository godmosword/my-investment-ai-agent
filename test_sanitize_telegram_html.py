from main import sanitize_telegram_html


def test_pre_tag_is_not_allowed_anymore():
    out = sanitize_telegram_html("<pre>secret</pre><code>ok</code>")
    assert "<pre>" not in out
    assert "</pre>" not in out
    assert "<code>ok</code>" in out


def test_supported_tags_are_preserved():
    src = '<b>x</b><i>y</i><u>z</u><s>w</s><blockquote>q</blockquote><a href="https://a.b">l</a>'
    out = sanitize_telegram_html(src)
    assert "<b>x</b>" in out
    assert "<i>y</i>" in out
    assert "<u>z</u>" in out
    assert "<s>w</s>" in out
    assert "<blockquote>q</blockquote>" in out
    assert '<a href="https://a.b">l</a>' in out
