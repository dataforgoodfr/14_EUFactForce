"""Central parser configuration registry for parsing and scoring scripts."""

from __future__ import annotations

from typing import Iterable

# Base parser configurations used by benchmark extraction.
CONFIGS: dict[str, dict[str, object]] = {
    "llamaparse_text": {"type": "llamaparse", "result_type": "text"},
    "llamaparse_markdown": {"type": "llamaparse", "result_type": "markdown"},
    "pymupdf": {"type": "pymupdf"},
    "docling_text": {"type": "docling", "result_type": "text", "postprocess": True},
    "docling_markdown": {
        "type": "docling",
        "result_type": "markdown",
        "postprocess": True,
        "indexing_cleanup": True,
    },
}

# Base benchmark profiles.
CONFIG_PROFILES: dict[str, list[str]] = {
    "full": list(CONFIGS.keys()),
    "fast": [
        "pymupdf",
        "docling_markdown",
        "llamaparse_markdown",
    ],
    "docling_only": [
        "docling_text",
        "docling_markdown",
    ],
}

def get_scoring_configs() -> list[str]:
    """Return all scoring config names."""
    return list(CONFIGS.keys())


def get_scoring_profiles() -> dict[str, list[str]]:
    """Return scoring profiles."""
    return {
        "full": get_scoring_configs(),
        "fast": list(CONFIG_PROFILES["fast"]),
        "docling_only": list(CONFIG_PROFILES["docling_only"]),
    }


def deduplicate_parser_config_names(names: Iterable[str]) -> list[str]:
    """De-duplicate parser config names while preserving order."""
    deduplicated: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduplicated.append(name)
    return deduplicated