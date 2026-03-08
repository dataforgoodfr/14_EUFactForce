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


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap.")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def split_into_paragraph_chunks(
    text: str,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text into paragraph-bounded chunks with size constraints."""
    if max_chunk_chars <= overlap_chars:
        raise ValueError("max_chunk_chars must be strictly greater than overlap_chars.")

    paragraphs = _normalize_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chunk_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                _split_long_text(
                    paragraph,
                    chunk_size=max_chunk_chars,
                    overlap=overlap_chars,
                )
            )
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chunk_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks
