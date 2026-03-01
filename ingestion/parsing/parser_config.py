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

# Dataset suffixes that quality scoring expects.
SCORING_SUFFIXES: tuple[str, ...] = ("", "_preprocessed", "_column")


def _expand_with_suffixes(
    base_names: Iterable[str],
    suffixes: Iterable[str],
) -> list[str]:
    expanded: list[str] = []
    for name in base_names:
        for suffix in suffixes:
            expanded.append(f"{name}{suffix}")
    return expanded


def get_scoring_configs() -> list[str]:
    """Return all scoring config names (base + dataset suffix variants)."""
    return _expand_with_suffixes(CONFIGS.keys(), SCORING_SUFFIXES)


def get_scoring_profiles() -> dict[str, list[str]]:
    """Return scoring profiles including suffix variants where appropriate."""
    return {
        "full": get_scoring_configs(),
        "fast": [
            "pymupdf",
            "pymupdf_preprocessed",
            "docling_markdown",
        ],
        "docling_only": _expand_with_suffixes(
            CONFIG_PROFILES["docling_only"],
            SCORING_SUFFIXES,
        ),
    }


_ALIAS_PREFIX_MAP: dict[str, str] = {
    "docling_postprocess_markdown": "docling_markdown",
}

_SUFFIX_ALIAS_MAP: dict[str, str] = {
    "": "",
    "_preprocessed": "_preprocessed",
    "_clean": "_preprocessed",
    "_column": "_column",
}


def canonicalize_parser_config_name(name: str) -> str:
    """Map legacy aliases to canonical config names while preserving suffixes."""
    for suffix_alias, canonical_suffix in _SUFFIX_ALIAS_MAP.items():
        if suffix_alias and name.endswith(suffix_alias):
            base_name = name[: -len(suffix_alias)]
            canonical_base = _ALIAS_PREFIX_MAP.get(base_name, base_name)
            return f"{canonical_base}{canonical_suffix}"

    return _ALIAS_PREFIX_MAP.get(name, name)


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
