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
    excluded, overrides = ingest.load_known_issues()
    assert "melissa" in excluded
    assert "elena-verna-20" in overrides
    assert overrides["elena-verna-20"] == 0.15


def test_load_known_issues_returns_empty_dicts_when_file_missing(tmp_path):
    excluded, overrides = ingest.load_known_issues(path=tmp_path / "does-not-exist.json")
    assert excluded == {}
    assert overrides == {}


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
    excluded_folders, _ = ingest.load_known_issues()
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
