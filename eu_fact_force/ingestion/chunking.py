"""Chunking helpers for ingestion parsing."""

from __future__ import annotations

import re

MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200

_RE_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_HAS_ALPHANUM = re.compile(r"[A-Za-z0-9]")


def _normalize_paragraphs(text: str) -> list[str]:
    """Normalize text into a list of non-empty paragraphs.

    - Normalize line endings (CRLF/CR to LF).
    - Split on blank lines.
    - For each segment: collapse internal whitespace to a single space, strip.
    - Drop empty segments and segments with no alphanumeric characters.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_paragraphs = _RE_PARAGRAPH_SPLIT.split(normalized)
    paragraphs: list[str] = []
    for paragraph in raw_paragraphs:
        compact = _RE_WHITESPACE.sub(" ", paragraph).strip()
        if compact and _RE_HAS_ALPHANUM.search(compact):
            paragraphs.append(compact)
    return paragraphs


def _split_into_fixed_size_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a single string into chunks of at most chunk_size chars with overlap.

    Consecutive chunks overlap by `overlap` characters. Each chunk is stripped
    of leading/trailing whitespace; empty chunks are omitted.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap.")

    step = chunk_size - overlap
    return [
        chunk
        for start in range(0, len(text), step)
        if (chunk := text[start : min(start + chunk_size, len(text))].strip())
    ]


def _try_append_paragraph(
    chunk_in_progress: str, paragraph: str, max_chunk_chars: int
) -> tuple[str, str | None]:
    """Try to append paragraph to current chunk; if over limit, flush current.
    Returns (next chunk_in_progress, completed_chunk or None).
    """
    candidate = (
        paragraph if not chunk_in_progress else f"{chunk_in_progress}\n\n{paragraph}"
    )
    if len(candidate) <= max_chunk_chars:
        return (candidate, None)
    return (paragraph, chunk_in_progress)


def _flush_and_split_long_paragraph(
    chunks: list[str],
    chunk_in_progress: str,
    paragraph: str,
    max_chunk_chars: int,
    overlap_chars: int,
) -> tuple[list[str], str]:
    """Flush current chunk to list (if any), extend with fixed-size pieces of paragraph.

    Returns (updated chunks, ""). No chunk in progress after flushing.
    """
    updated_chunks = list(chunks)
    if chunk_in_progress:
        updated_chunks.append(chunk_in_progress)
    updated_chunks.extend(
        _split_into_fixed_size_chunks(
            paragraph,
            chunk_size=max_chunk_chars,
            overlap=overlap_chars,
        )
    )
    return (updated_chunks, "")


def _merge_or_flush_paragraph(
    chunks: list[str],
    current_chunk_in_progress: str,
    paragraph: str,
    max_chunk_chars: int,
) -> tuple[list[str], str]:
    """Merge paragraph into current chunk or flush and start new one.

    Returns (updated chunks, next chunk_in_progress). When merge would exceed
    limit, the completed chunk is included in the returned list.
    """
    next_chunk_in_progress, completed_chunk = _try_append_paragraph(
        current_chunk_in_progress, paragraph, max_chunk_chars
    )
    if completed_chunk is not None: #paragraph was not merged
        return ([*chunks, completed_chunk], next_chunk_in_progress)
    return (chunks, next_chunk_in_progress) #paragraph was merged into chunks


def _accumulate_paragraphs_into_chunks(
    paragraphs: list[str],
    max_chunk_chars: int,
    overlap_chars: int,
) -> list[str]:
    """Build chunks from paragraphs: merge until size limit, then flush; split long paragraphs."""
    chunks: list[str] = []
    chunk_in_progress = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chunk_chars:
            chunks, chunk_in_progress = _flush_and_split_long_paragraph(
                chunks, chunk_in_progress, paragraph, max_chunk_chars, overlap_chars
            )
        else:
            chunks, chunk_in_progress = _merge_or_flush_paragraph(
                chunks, chunk_in_progress, paragraph, max_chunk_chars
            )

    if chunk_in_progress:
        chunks = [*chunks, chunk_in_progress]
    return chunks


def split_into_paragraph_chunks(
    text: str,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text into paragraph-bounded chunks with size constraints.

    The size limit (max_chunk_chars) is intended for downstream use such as
    embedding models and retrieval; chunks are kept within this bound.
    """
    if max_chunk_chars <= overlap_chars:
        raise ValueError("max_chunk_chars must be strictly greater than overlap_chars.")

    paragraphs = _normalize_paragraphs(text)
    if not paragraphs:
        return []
    return _accumulate_paragraphs_into_chunks(
        paragraphs, max_chunk_chars, overlap_chars
    )
