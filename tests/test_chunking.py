from chunking import (
    MAX_CHUNK_TOKENS,
    MIN_CHUNK_TOKENS,
    ParagraphBlock,
    group_into_chunks,
    parse_transcript,
)

SAMPLE_TRANSCRIPT = """
Ada Chen Rekhi (00:00:00):
It's a terrible outcome to wake up one day and be late career.

Lenny (00:00:36):
Welcome to Lenny's Podcast, where I interview world-class product leaders.

(00:01:21):
We do a live exercise around my own personal values.

Ada Chen Rekhi (00:03:20):
Thanks. I'm excited to be here.
"""


def test_parse_transcript_attributes_named_speakers():
    blocks = parse_transcript(SAMPLE_TRANSCRIPT)
    assert blocks[0].speaker == "Ada Chen Rekhi"
    assert blocks[0].timestamp_seconds == 0
    assert blocks[1].speaker == "Lenny"
    assert blocks[1].timestamp_seconds == 36


def test_parse_transcript_attributes_continuation_to_last_speaker():
    blocks = parse_transcript(SAMPLE_TRANSCRIPT)
    # third block is a bare "(00:01:21):" continuation -- must inherit "Lenny"
    assert blocks[2].speaker == "Lenny"
    assert blocks[2].timestamp_seconds == 81
    assert "live exercise" in blocks[2].text


def test_parse_transcript_does_not_bridge_paragraph_text_into_speaker():
    # Regression test: a naive regex using \s+ between speaker and the
    # timestamp marker can bridge across the blank line separating a
    # paragraph from the next marker, capturing the whole paragraph as
    # the "speaker" name. Every parsed speaker must be short.
    blocks = parse_transcript(SAMPLE_TRANSCRIPT)
    for block in blocks:
        assert len(block.speaker) < 50, block.speaker


def test_parse_transcript_supports_mm_ss_timestamps():
    # ~10% of the corpus uses "(MM:SS)" instead of "(HH:MM:SS)" for shorter
    # episodes (e.g. seth-godin, teresa-torres) -- found during
    # implementation, not grooming (both transcripts checked while grooming
    # happened to use HH:MM:SS).
    transcript = (
        "Lenny (00:00):\n"
        "Welcome to the show.\n\n"
        "Seth Godin (00:10):\n"
        "Thanks for having me.\n"
    )
    blocks = parse_transcript(transcript)
    assert len(blocks) == 2
    assert blocks[0].speaker == "Lenny"
    assert blocks[0].timestamp_seconds == 0
    assert blocks[1].speaker == "Seth Godin"
    assert blocks[1].timestamp_seconds == 10


def test_group_into_chunks_respects_token_targets():
    # Build a synthetic transcript with enough content to require grouping
    # multiple paragraph blocks into each chunk.
    blocks = [
        ParagraphBlock("Speaker", i * 10, "word " * 100)
        for i in range(20)
    ]
    chunks = group_into_chunks(blocks, overlap_pct=0.0)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:  # last chunk may be a shorter remainder
        assert MIN_CHUNK_TOKENS <= chunk.token_count <= MAX_CHUNK_TOKENS


def test_group_into_chunks_no_overlap_does_not_repeat_content():
    blocks = [ParagraphBlock("Speaker", i * 10, "word " * 100) for i in range(20)]
    chunks = group_into_chunks(blocks, overlap_pct=0.0)
    combined = "\n".join(c.text for c in chunks)
    # each block's marker text should appear exactly once across all chunks
    assert combined.count("Speaker: word") == len(blocks)


def test_group_into_chunks_with_overlap_repeats_trailing_content():
    blocks = [ParagraphBlock("Speaker", i * 10, "word " * 100) for i in range(20)]
    no_overlap = group_into_chunks(blocks, overlap_pct=0.0)
    with_overlap = group_into_chunks(blocks, overlap_pct=0.15)
    combined = "\n".join(c.text for c in with_overlap)
    # with overlap, at least one block's text is repeated across chunk boundaries
    assert combined.count("Speaker: word") > len(blocks)
    assert len(with_overlap) >= len(no_overlap)


def test_oversized_single_block_is_split_not_dropped():
    huge_text = "This is one sentence. " * 200  # forces > MAX_CHUNK_TOKENS
    blocks = [ParagraphBlock("Speaker", 0, huge_text)]
    chunks = group_into_chunks(blocks, overlap_pct=0.0)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= MAX_CHUNK_TOKENS
