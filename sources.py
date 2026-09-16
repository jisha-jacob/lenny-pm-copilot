"""Sources rendering: turn an answer's cited chunks (issue #5) into a
clean, deduped Sources list (see issue #6, _docs/plan.md section 6).
"""


def _anchored_url(youtube_url: str, start_timestamp) -> str:
    if start_timestamp is None:
        return youtube_url
    separator = "&" if "?" in youtube_url else "?"
    return f"{youtube_url}{separator}t={start_timestamp}s"


def render_sources(cited_chunks: list[dict]) -> list[dict]:
    """Dedupe `cited_chunks` (the shape `retrieval.retrieve` / issue #5's
    `cited_chunks` return) by `video_id` into one Sources entry per
    episode: `guest`, `title`, and a `url` anchored to the earliest cited
    timestamp for that episode (or the plain `youtube_url` if no cited
    chunk for it has a timestamp). Entries are ordered by first appearance
    in `cited_chunks`.
    """
    best_timestamp: dict[str, object] = {}
    entries: dict[str, dict] = {}
    order: list[str] = []

    for chunk in cited_chunks:
        video_id = chunk["video_id"]
        timestamp = chunk.get("start_timestamp")

        if video_id not in entries:
            entries[video_id] = {
                "guest": chunk["guest"],
                "title": chunk["title"],
                "youtube_url": chunk["youtube_url"],
            }
            best_timestamp[video_id] = timestamp
            order.append(video_id)
        elif timestamp is not None and (
            best_timestamp[video_id] is None or timestamp < best_timestamp[video_id]
        ):
            best_timestamp[video_id] = timestamp

    return [
        {
            "guest": entries[video_id]["guest"],
            "title": entries[video_id]["title"],
            "url": _anchored_url(
                entries[video_id]["youtube_url"], best_timestamp[video_id]
            ),
        }
        for video_id in order
    ]
