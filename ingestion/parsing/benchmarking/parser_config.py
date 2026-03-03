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


def canonicalize_parser_config_name(name: str) -> str:
    """Return canonical config name."""
    return name


def canonicalize_parser_config_names(names: Iterable[str]) -> list[str]:
    """Canonicalize and de-duplicate while preserving order."""
    canonicalized: list[str] = []
    seen: set[str] = set()
    for name in names:
        canonical = canonicalize_parser_config_name(name)
        if canonical in seen:
            continue
        seen.add(canonical)
        canonicalized.append(canonical)
    return canonicalized

