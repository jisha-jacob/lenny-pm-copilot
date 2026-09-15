"""Transcript parsing and chunking (see _docs/plan.md section 5).

Transcript body format, confirmed by inspecting real transcript.md files
during grooming and implementation of issue #3:
  - A new speaker turn starts with a line "Speaker Name (TIMESTAMP):".
  - A same-speaker continuation paragraph starts with a bare "(TIMESTAMP):"
    line (source pre-splits long monologues into multiple blocks).
  - TIMESTAMP is "HH:MM:SS" for longer episodes, but "MM:SS" for shorter
    ones (~10% of the corpus, e.g. seth-godin, teresa-torres, marc-benioff
    -- found while implementing, not caught during grooming since the two
    transcripts inspected then both happened to use HH:MM:SS).
Each such marker line is followed by one paragraph of text, then a blank
line, then the next marker.
"""

import re
from dataclasses import dataclass

import tiktoken

_MARKER_RE = re.compile(
    # Speaker (if present) and the timestamp must be on the same physical
    # line -- horizontal whitespace only, never \s+, which would also match
    # \n and let this bridge across the blank line into the next paragraph.
    # The hours component is optional: shorter episodes use "MM:SS".
    r"^(?:(?P<speaker>[^\n]+?)[ \t]+)?\((?:(?P<h>\d{1,2}):)?(?P<m>\d{2}):(?P<s>\d{2})\):[ \t]*$",
    re.MULTILINE,
)

_ENCODING = tiktoken.get_encoding("cl100k_base")

MIN_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 800


@dataclass
class ParagraphBlock:
    speaker: str
    timestamp_seconds: int
    text: str


@dataclass
class Chunk:
    text: str
    start_timestamp: int
    token_count: int


def _token_count(text: str) -> int:
    return len(_ENCODING.encode(text))


def parse_transcript(body: str) -> list[ParagraphBlock]:
    """Split a transcript body into paragraph blocks in order."""
    matches = list(_MARKER_RE.finditer(body))
    blocks: list[ParagraphBlock] = []
    last_speaker = None
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()
        if not text:
            continue
        speaker = match.group("speaker")
        if speaker:
            last_speaker = speaker.strip()
        elif last_speaker is None:
            # Marker with no preceding named speaker and no text yet --
            # skip rather than guess.
            continue
        hours = int(match.group("h")) if match.group("h") else 0
        timestamp_seconds = hours * 3600 + int(match.group("m")) * 60 + int(match.group("s"))
        blocks.append(ParagraphBlock(last_speaker, timestamp_seconds, text))
    return blocks


def _formatted(block: ParagraphBlock) -> str:
    """The exact text a block contributes to a chunk (speaker-prefixed) --
    used consistently for token accounting so decisions here match what
    actually ends up in the assembled chunk_text."""
    return f"{block.speaker}: {block.text}"


# Leaves headroom for the "Speaker: " prefix and "\n\n" join separators
# added when blocks are assembled into a chunk, so the final chunk_text
# reliably stays at or under MAX_CHUNK_TOKENS.
_SAFETY_MARGIN_TOKENS = 20


def _split_oversized_block(block: ParagraphBlock) -> list[ParagraphBlock]:
    """Fallback: split a single paragraph block that alone exceeds
    MAX_CHUNK_TOKENS at sentence boundaries, so it never silently gets
    dropped or crashes the chunker."""
    if _token_count(_formatted(block)) <= MAX_CHUNK_TOKENS - _SAFETY_MARGIN_TOKENS:
        return [block]
    sentences = re.split(r"(?<=[.!?])\s+", block.text)
    sub_blocks = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        candidate_block = ParagraphBlock(block.speaker, block.timestamp_seconds, candidate)
        if current and _token_count(_formatted(candidate_block)) > MAX_CHUNK_TOKENS - _SAFETY_MARGIN_TOKENS:
            sub_blocks.append(ParagraphBlock(block.speaker, block.timestamp_seconds, current))
            current = sentence
        else:
            current = candidate
    if current:
        sub_blocks.append(ParagraphBlock(block.speaker, block.timestamp_seconds, current))
    return sub_blocks


def group_into_chunks(
    blocks: list[ParagraphBlock], overlap_pct: float = 0.0
) -> list[Chunk]:
    """Group consecutive paragraph blocks into ~500-800 token chunks.

    overlap_pct controls how much of the trailing content of one chunk is
    repeated at the start of the next (by re-including trailing blocks),
    kept as a parameter rather than a fixed value so issue #8's golden-set
    eval can compare overlap settings without code changes.
    """
    expanded: list[ParagraphBlock] = []
    for block in blocks:
        expanded.extend(_split_oversized_block(block))

    chunks: list[Chunk] = []
    i = 0
    n = len(expanded)
    while i < n:
        texts = []
        token_total = 0
        start_ts = expanded[i].timestamp_seconds
        j = i
        while j < n:
            formatted = _formatted(expanded[j])
            block_tokens = _token_count(formatted)
            if texts and token_total + block_tokens > MAX_CHUNK_TOKENS - _SAFETY_MARGIN_TOKENS:
                break
            texts.append(formatted)
            token_total += block_tokens
            j += 1
            if token_total >= MIN_CHUNK_TOKENS:
                break
        chunk_text = "\n\n".join(texts)
        chunks.append(Chunk(chunk_text, start_ts, _token_count(chunk_text)))

        if j >= n:
            break

        if overlap_pct > 0:
            overlap_budget = token_total * overlap_pct
            back = j - 1
            consumed = 0
            while back > i and consumed < overlap_budget:
                consumed += _token_count(expanded[back].text)
                back -= 1
            i = max(back + 1, i + 1)
        else:
            i = j
    return chunks
