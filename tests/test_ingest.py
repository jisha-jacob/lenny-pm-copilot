import json
import sys

import ingest


def _write_episode(dir_path, guest, title, video_id):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "transcript.md").write_text(
        f"""---
guest: {guest}
title: {title}
youtube_url: https://www.youtube.com/watch?v={video_id}
video_id: {video_id}
publish_date: 2024-01-01
---

## Transcript

{guest} (00:00:00):
Some real transcript content for this episode.
""",
        encoding="utf-8",
    )


def test_load_known_issues_reads_the_real_checked_in_config():
    # This is the actual file ingest.py consults at runtime -- not a fixture.
    excluded, overrides, metadata_overrides = ingest.load_known_issues()
    assert "melissa" in excluded
    assert "elena-verna-20" in overrides
    assert overrides["elena-verna-20"] == 0.15
    assert metadata_overrides["peter-deng"]["video_id"] == "8TpakBfsmcQ"
    assert metadata_overrides["daniel-lereya"]["video_id"] == "L9qqwV8_rvY"


def test_load_known_issues_returns_empty_dicts_when_file_missing(tmp_path):
    excluded, overrides, metadata_overrides = ingest.load_known_issues(
        path=tmp_path / "does-not-exist.json"
    )
    assert excluded == {}
    assert overrides == {}
    assert metadata_overrides == {}


def test_main_skips_a_known_excluded_folder_and_processes_a_normal_one(
    tmp_path, monkeypatch, capsys
):
    """Runs ingest.py's real main() against a fake repo containing one folder
    that matches a real entry in the checked-in known_issues.json exclusion
    list, and one ordinary folder. The excluded folder must be skipped (with
    its reason logged) and never embedded/upserted; the ordinary one must be
    processed normally. DB and the embedding model are mocked -- this test
    is about the skip mechanism, not ingestion end-to-end.
    """
    excluded_folders, _, _ = ingest.load_known_issues()
    assert excluded_folders, "expected the real known_issues.json to be non-empty"
    excluded_name = next(iter(excluded_folders))

    repo_dir = tmp_path / "repo"
    episodes_dir = repo_dir / "episodes"
    _write_episode(
        episodes_dir / excluded_name,
        guest="Should Not Matter",
        title="This should never be read",
        video_id="EXCLUDEDVIDEOID",
    )
    _write_episode(
        episodes_dir / "a-normal-episode",
        guest="Normal Guest",
        title="A totally normal episode | Normal Guest",
        video_id="NORMALVIDEOID",
    )

    monkeypatch.setattr(ingest, "sync_repo", lambda repo_dir: None)

    embedded_for = []

    def fake_embed_documents(texts):
        embedded_for.append(texts)
        return [[0.0] * 768 for _ in texts]

    monkeypatch.setattr(ingest, "embed_documents", fake_embed_documents)

    upserted_folders = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            chunk_id = params[0]
            upserted_folders.append(chunk_id)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ingest.db, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(ingest.db, "ensure_schema", lambda conn: None)

    monkeypatch.setattr(
        sys, "argv", ["ingest.py", "--repo-dir", str(repo_dir)]
    )

    ingest.main()

    out = capsys.readouterr().out
    assert f"SKIP {excluded_name}: known issue -- {excluded_folders[excluded_name]}" in out

    # The excluded folder's video_id must never appear in anything embedded
    # or upserted -- proves it was actually skipped, not just logged.
    assert not any("EXCLUDEDVIDEOID" in cid for cid in upserted_folders)
    assert not any(
        "Should Not Matter" in text for texts in embedded_for for text in texts
    )

    # The normal episode must still have been processed.
    assert any("NORMALVIDEOID" in cid for cid in upserted_folders)


def test_load_episode_applies_metadata_overrides_before_required_field_check(tmp_path):
    episode_dir = tmp_path / "peter-deng"
    episode_dir.mkdir()
    (episode_dir / "transcript.md").write_text(
        """---
guest: Peter Deng
title: Peter Deng
youtube_url: ''
video_id: ''
description: ''
duration_seconds: 0
---

## Transcript

Peter Deng (00:00:00):
Some real transcript content for this episode.
""",
        encoding="utf-8",
    )

    without_override = ingest.load_episode(episode_dir / "transcript.md")
    assert without_override is None  # missing video_id and publish_date

    with_override = ingest.load_episode(
        episode_dir / "transcript.md",
        metadata_overrides={
            "youtube_url": "https://www.youtube.com/watch?v=8TpakBfsmcQ",
            "video_id": "8TpakBfsmcQ",
            "publish_date": "2025-06-22",
        },
    )
    assert with_override is not None
    assert with_override.metadata["video_id"] == "8TpakBfsmcQ"
    assert with_override.metadata["publish_date"] == "2025-06-22"
    assert with_override.metadata["guest"] == "Peter Deng"  # untouched fields preserved


def test_main_recovers_peter_deng_and_daniel_lereya_via_real_metadata_overrides(
    tmp_path, monkeypatch
):
    """Integration-style test mirroring the known-exclusion test above, but
    for issue #18's metadata_overrides: builds fake peter-deng/daniel-lereya
    folders shaped like the real corpus bug (empty video_id/youtube_url,
    missing publish_date) and verifies ingest.py's real, checked-in
    known_issues.json overrides recover them rather than skipping."""
    _, _, metadata_overrides = ingest.load_known_issues()
    assert "peter-deng" in metadata_overrides
    assert "daniel-lereya" in metadata_overrides

    repo_dir = tmp_path / "repo"
    episodes_dir = repo_dir / "episodes"
    for name, guest in [("peter-deng", "Peter Deng"), ("daniel-lereya", "Daniel Lereya")]:
        d = episodes_dir / name
        d.mkdir(parents=True)
        (d / "transcript.md").write_text(
            f"""---
guest: {guest}
title: {guest}
youtube_url: ''
video_id: ''
description: ''
duration_seconds: 0
---

## Transcript

{guest} (00:00:00):
Some real transcript content for this episode.
""",
            encoding="utf-8",
        )

    monkeypatch.setattr(ingest, "sync_repo", lambda repo_dir: None)
    monkeypatch.setattr(
        ingest, "embed_documents", lambda texts: [[0.0] * 768 for _ in texts]
    )

    upserted = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            upserted.append(params)

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ingest.db, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(ingest.db, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(sys, "argv", ["ingest.py", "--repo-dir", str(repo_dir)])

    ingest.main()

    upserted_video_ids = {params[4] for params in upserted}
    assert upserted_video_ids == {"8TpakBfsmcQ", "L9qqwV8_rvY"}


def test_main_video_id_filter_only_ingests_matching_episodes(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    episodes_dir = repo_dir / "episodes"
    _write_episode(
        episodes_dir / "episode-a", guest="A", title="A", video_id="VIDEOA"
    )
    _write_episode(
        episodes_dir / "episode-b", guest="B", title="B", video_id="VIDEOB"
    )

    monkeypatch.setattr(ingest, "sync_repo", lambda repo_dir: None)
    monkeypatch.setattr(
        ingest, "embed_documents", lambda texts: [[0.0] * 768 for _ in texts]
    )

    upserted_video_ids = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            upserted_video_ids.append(params[4])  # video_id column

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ingest.db, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(ingest.db, "ensure_schema", lambda conn: None)

    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest.py", "--repo-dir", str(repo_dir), "--video-id", "VIDEOB"],
    )

    ingest.main()

    assert upserted_video_ids == ["VIDEOB"]
