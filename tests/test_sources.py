import sources


def _chunk(**overrides):
    base = {
        "chunk_id": "abc123:ov0.0:0000",
        "guest": "Shreyas Doshi",
        "title": "The art of product management",
        "youtube_url": "https://youtube.com/watch?v=abc123",
        "video_id": "abc123",
        "publish_date": "2021-01-01",
        "start_timestamp": 42,
        "chunk_text": "Prioritization is about saying no to good ideas.",
        "distance": 0.12,
    }
    base.update(overrides)
    return base


def test_render_sources_empty_input_returns_empty_list():
    assert sources.render_sources([]) == []


def test_render_sources_dedupes_multiple_chunks_from_same_episode():
    chunks = [
        _chunk(chunk_id="abc123:ov0.0:0000", start_timestamp=42),
        _chunk(chunk_id="abc123:ov0.0:0001", start_timestamp=90),
    ]

    result = sources.render_sources(chunks)

    assert len(result) == 1


def test_render_sources_returns_only_guest_title_url():
    result = sources.render_sources([_chunk()])

    assert result == [
        {
            "guest": "Shreyas Doshi",
            "title": "The art of product management",
            "url": "https://youtube.com/watch?v=abc123&t=42s",
        }
    ]


def test_render_sources_uses_question_mark_when_url_has_no_query_string():
    result = sources.render_sources(
        [_chunk(youtube_url="https://youtu.be/abc123", start_timestamp=42)]
    )

    assert result[0]["url"] == "https://youtu.be/abc123?t=42s"


def test_render_sources_falls_back_to_plain_url_when_timestamp_missing():
    result = sources.render_sources([_chunk(start_timestamp=None)])

    assert result[0]["url"] == "https://youtube.com/watch?v=abc123"


def test_render_sources_treats_zero_timestamp_as_present():
    result = sources.render_sources([_chunk(start_timestamp=0)])

    assert result[0]["url"] == "https://youtube.com/watch?v=abc123&t=0s"


def test_render_sources_uses_earliest_timestamp_across_cited_chunks():
    chunks = [
        _chunk(chunk_id="abc123:ov0.0:0002", start_timestamp=200),
        _chunk(chunk_id="abc123:ov0.0:0000", start_timestamp=42),
        _chunk(chunk_id="abc123:ov0.0:0001", start_timestamp=90),
    ]

    result = sources.render_sources(chunks)

    assert result[0]["url"] == "https://youtube.com/watch?v=abc123&t=42s"


def test_render_sources_earliest_timestamp_ignores_missing_ones():
    chunks = [
        _chunk(chunk_id="abc123:ov0.0:0000", start_timestamp=None),
        _chunk(chunk_id="abc123:ov0.0:0001", start_timestamp=90),
    ]

    result = sources.render_sources(chunks)

    assert result[0]["url"] == "https://youtube.com/watch?v=abc123&t=90s"


def test_render_sources_preserves_order_of_first_appearance():
    chunks = [
        _chunk(
            chunk_id="def456:ov0.0:0000",
            video_id="def456",
            guest="Elena Verna",
            title="Product-led sales",
            youtube_url="https://youtube.com/watch?v=def456",
            start_timestamp=10,
        ),
        _chunk(chunk_id="abc123:ov0.0:0000", start_timestamp=42),
        _chunk(
            chunk_id="def456:ov0.0:0001",
            video_id="def456",
            guest="Elena Verna",
            title="Product-led sales",
            youtube_url="https://youtube.com/watch?v=def456",
            start_timestamp=20,
        ),
    ]

    result = sources.render_sources(chunks)

    assert [entry["guest"] for entry in result] == ["Elena Verna", "Shreyas Doshi"]
