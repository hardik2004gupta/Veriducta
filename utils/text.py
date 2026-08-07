"""Text processing and approximate token counting utilities."""

import re

# Characters-per-token approximation for English prose.
# Used by count_tokens AND by the chunker's sliding window to stay consistent:
# changing this value affects both how chunks are measured and how windows are sized.
CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Approximate BPE token count for English text.

    Uses a character-based heuristic (``CHARS_PER_TOKEN`` chars ≈ 1 token),
    consistent with GPT/BERT BPE behaviour for English prose.

    Args:
        text: Input text string.

    Returns:
        Estimated token count, minimum 1.
    """
    return max(1, len(text) // CHARS_PER_TOKEN)


def find_boundary_offsets(text: str, patterns: list[str]) -> list[int]:
    """Return sorted character offsets where section boundaries occur in *text*.

    Args:
        text: Full text to scan.
        patterns: Regex patterns whose match positions mark boundaries.

    Returns:
        Sorted list of character offsets (start positions of each match).
    """
    if not patterns:
        return []
    combined = re.compile("|".join(patterns))
    return sorted(m.start() for m in combined.finditer(text))


def split_at_boundaries(text: str, patterns: list[str]) -> list[str]:
    """Split *text* into segments at every section boundary match.

    The boundary marker text is kept at the **beginning** of the following
    segment so every segment starts with its own heading.

    Args:
        text: Full document text.
        patterns: Regex patterns that mark section boundaries.

    Returns:
        Non-empty list of text segments in document order.
    """
    if not patterns or not text.strip():
        return [text] if text.strip() else []

    offsets = find_boundary_offsets(text, patterns)
    if not offsets:
        return [text]

    segments: list[str] = []
    prev = 0
    for off in offsets:
        chunk = text[prev:off]
        if chunk.strip():
            segments.append(chunk)
        prev = off
    tail = text[prev:]
    if tail.strip():
        segments.append(tail)
    return segments
