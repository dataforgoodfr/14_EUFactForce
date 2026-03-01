"""Constants used by Docling postprocessing helpers."""

from __future__ import annotations

# Minimum token-overlap ratio between Docling and PyMuPDF text
# for considering a candidate block as real (not ghost OCR).
DOCLING_PYMUPDF_MIN_TOKEN_OVERLAP_RATIO = 0.2
# Absolute token-overlap floor used with the ratio threshold above.
DOCLING_PYMUPDF_MIN_SHARED_TOKENS = 1
# If this much of a text block overlaps a picture area, drop the block.
DOCLING_PICTURE_OVERLAP_DROP_RATIO = 0.6
# If this much of the block is picture-overlapped, avoid using it for
# snippet-based cleanup decisions.
DOCLING_PICTURE_OVERLAP_BLOCK_RATIO = 0.5
# Maximum page-area ratio to treat a bbox as a "small box" candidate.
DOCLING_SMALL_BOX_MAX_AREA_RATIO = 0.0015
# Minimum character length for line-level removal from small-box snippets.
DOCLING_SMALL_BOX_LINE_REMOVE_MIN_CHARS = 2

# Front-matter labels that hierarchical postprocessing can demote to plain text.
DEMOTED_HEADER_LABELS = {
    "review",
    "abstract",
    "addresses",
    "keywords",
}
