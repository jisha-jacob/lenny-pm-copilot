"""Ingest Lenny's Podcast transcripts into the lenny_pm_copilot database.

Reads episodes/{guest}/transcript.md from ChatPRD/lennys-podcast-transcripts
(cloned/pulled into a local cache dir), chunks each transcript, embeds each
chunk with nomic-embed-text (via embeddings.py), and upserts vector +
metadata into Postgres (see issue #3, _docs/plan.md sections 5-6).

Usage:
    python ingest.py [--overlap-pct 0.15] [--limit 5] [--repo-dir DIR]
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import frontmatter

import db
from chunking import group_into_chunks, parse_transcript
from embeddings import embed_documents

REPO_URL = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"
DEFAULT_REPO_DIR = Path(".cache/lennys-podcast-transcripts")
REQUIRED_FIELDS = ["guest", "title", "youtube_url", "video_id", "publish_date"]

UPSERT_SQL = """
    INSERT INTO chunks (
        chunk_id, guest, title, youtube_url, video_id,
        publish_date, start_timestamp, chunk_text, embedding
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (chunk_id) DO UPDATE SET
        guest = EXCLUDED.guest,
        title = EXCLUDED.title,
        youtube_url = EXCLUDED.youtube_url,
        video_id = EXCLUDED.video_id,
        publish_date = EXCLUDED.publish_date,
        start_timestamp = EXCLUDED.start_timestamp,
        chunk_text = EXCLUDED.chunk_text,
        embedding = EXCLUDED.embedding;
"""


def sync_repo(repo_dir: Path) -> None:
    if repo_dir.exists():
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True)
    else:
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(repo_dir)], check=True
        )


def load_episode(path: Path):
    post = frontmatter.load(path)
    missing = [f for f in REQUIRED_FIELDS if not post.metadata.get(f)]
    if missing:
        print(f"SKIP {path}: missing required frontmatter field(s) {missing}")
        return None
    return post


def normalize_publish_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlap-pct", type=float, default=0.0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--repo-dir", type=Path, default=DEFAULT_REPO_DIR)
    args = parser.parse_args()

    sync_repo(args.repo_dir)
    episode_dirs = sorted((args.repo_dir / "episodes").iterdir())
    episode_dirs = episode_dirs[args.start :]
    if args.limit:
        episode_dirs = episode_dirs[: args.limit]

    conn = db.get_connection()
    db.ensure_schema(conn)

    processed = 0
    skipped = 0
    total_chunks = 0

    for episode_dir in episode_dirs:
        transcript_path = episode_dir / "transcript.md"
        if not transcript_path.exists():
            continue

        post = load_episode(transcript_path)
        if post is None:
            skipped += 1
            continue

        meta = post.metadata
        video_id = meta["video_id"]
        blocks = parse_transcript(post.content)
        chunks = group_into_chunks(blocks, overlap_pct=args.overlap_pct)

        if not chunks:
            print(f"SKIP {episode_dir.name}: no parseable transcript blocks")
            skipped += 1
            continue

        vectors = embed_documents([c.text for c in chunks])

        with conn.cursor() as cur:
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
                chunk_id = f"{video_id}:ov{args.overlap_pct}:{idx:04d}"
                cur.execute(
                    UPSERT_SQL,
                    (
                        chunk_id,
                        meta["guest"],
                        meta["title"],
                        meta["youtube_url"],
                        video_id,
                        normalize_publish_date(meta["publish_date"]),
                        chunk.start_timestamp,
                        chunk.text,
                        vector,
                    ),
                )
        conn.commit()

        processed += 1
        total_chunks += len(chunks)
        print(f"[{processed}/{len(episode_dirs)}] {episode_dir.name}: {len(chunks)} chunks")

    conn.close()
    print(
        f"Done. Episodes processed: {processed}, skipped: {skipped}, "
        f"total chunks written: {total_chunks}"
    )


if __name__ == "__main__":
    sys.exit(main())
