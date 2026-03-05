"""Chunking utilities for embedding benchmark."""

from __future__ import annotations

import re

from .benchmark_config import (
    CHUNK_OVERLAP_CHARS,
    CHUNK_SIZE_CHARS,
    CHUNKING_STRATEGY,
    VALID_CHUNKING_STRATEGIES,
)

PARAGRAPH_SEPARATOR = "\n\n"


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[str]:
    """Split text into overlapping fixed-size character chunks."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap.")

    chunks: list[str] = []
    start_index = 0
    text_len = len(text)
    while start_index < text_len:
        end_index = min(start_index + chunk_size, text_len)
        chunk = text[start_index:end_index].strip()
        if chunk:
            chunks.append(chunk)
        if end_index == text_len:
            break
        start_index = end_index - overlap
    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split markdown/text into non-empty paragraphs by blank lines."""
    raw_parts = re.split(r"\n\s*\n", text)
    return [part.strip() for part in raw_parts if part.strip()]


def _normalize_paragraph_parts(
    paragraphs: list[str], chunk_size: int, overlap: int
) -> list[str]:
    """
    Normalize paragraphs into paragraph parts used for chunk assembly.

    A paragraph part is either:
    - one full paragraph (when it already fits in chunk_size), or
    - one fixed-size sub-chunk of an oversized paragraph.
    """
    paragraph_parts: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            paragraph_parts.append(paragraph)
        else:
            paragraph_parts.extend(
                chunk_text(paragraph, chunk_size=chunk_size, overlap=overlap)
            )
    return paragraph_parts


def _build_paragraph_chunk(paragraph_parts: list[str]) -> str:
    return PARAGRAPH_SEPARATOR.join(paragraph_parts).strip()


def _collect_parts_for_chunk(
    paragraph_parts: list[str], start_part_index: int, chunk_size: int
) -> tuple[list[str], int]:
    """
    Collect as many paragraph parts as fit in one chunk.

    Returns the collected paragraph parts and the next read index.
    """
    current_paragraph_parts: list[str] = []
    current_len = 0
    end_index = start_part_index
    while end_index < len(paragraph_parts):
        paragraph_part = paragraph_parts[end_index]
        separator_len = len(PARAGRAPH_SEPARATOR) if current_paragraph_parts else 0
        candidate_len = current_len + separator_len + len(paragraph_part)
        if candidate_len > chunk_size and current_paragraph_parts:
            break
        current_paragraph_parts.append(paragraph_part)
        current_len = candidate_len
        end_index += 1
    return current_paragraph_parts, end_index


def _next_start_with_overlap(
    paragraph_parts: list[str], start_part_index: int, end_index: int, overlap_target: int
) -> int:
    if overlap_target <= 0:
        return end_index

    overlap_len = 0
    back = end_index - 1
    while back >= start_part_index:
        overlap_len += len(paragraph_parts[back])
        if back < end_index - 1:
            overlap_len += len(PARAGRAPH_SEPARATOR)
        if overlap_len >= overlap_target:
            break
        back -= 1
    return max(back + 1, start_part_index + 1)


def _chunk_paragraph_parts(
    paragraph_parts: list[str], chunk_size: int, overlap: int
) -> list[str]:
    """Assemble final chunks from normalized paragraph parts with overlap."""
    chunks: list[str] = []
    part_start_index = 0
    total_paragraph_parts = len(paragraph_parts)

    while part_start_index < total_paragraph_parts:
        current_paragraph_parts, end = _collect_parts_for_chunk(
            paragraph_parts, part_start_index, chunk_size
        )
        chunk = _build_paragraph_chunk(current_paragraph_parts)
        if chunk:
            chunks.append(chunk)
        if end >= total_paragraph_parts:
            break
        part_start_index = _next_start_with_overlap(
            paragraph_parts, part_start_index, end, overlap
        )

    return chunks


def chunk_text_by_paragraph(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[str]:
    """
    Split text into paragraph-aware chunks.

    A paragraph part is either a full paragraph or a split slice from an
    oversized paragraph. The chunker preserves paragraph boundaries when possible,
    while keeping chunk lengths bounded and applying paragraph-level overlap by 
    reusing trailing paragraphs.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap.")

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    paragraph_parts = _normalize_paragraph_parts(paragraphs, chunk_size, overlap)
    return _chunk_paragraph_parts(paragraph_parts, chunk_size, overlap)


def build_chunks(docs: dict[str, str], strategy: str = CHUNKING_STRATEGY) -> list[dict]:
    """Build chunk records with document and position metadata."""
    if strategy not in VALID_CHUNKING_STRATEGIES:
        raise ValueError(
            f"Unsupported chunking strategy '{strategy}'. "
            f"Expected one of {sorted(VALID_CHUNKING_STRATEGIES)}."
        )

    chunk_records: list[dict] = []
    for doc_id, text in docs.items():
        doc_chunks = (
            chunk_text_by_paragraph(text) if strategy == "paragraph" else chunk_text(text)
        )
        for index, chunk in enumerate(doc_chunks):
            chunk_records.append(
                {
                    "chunk_id": f"{doc_id}::chunk_{index}",
                    "doc_id": doc_id,
                    "chunk_index": index,
                    "text": chunk,
                }
            )

    print(
        f"Built {len(chunk_records)} chunks "
        f"(strategy={strategy}, size={CHUNK_SIZE_CHARS}, overlap={CHUNK_OVERLAP_CHARS})"
    )
    return chunk_records


def build_chunk_lookup(chunks: list[dict]) -> dict[str, dict]:
    """Return a lookup by chunk_id for pool export and inspection."""
    return {chunk["chunk_id"]: chunk for chunk in chunks}
