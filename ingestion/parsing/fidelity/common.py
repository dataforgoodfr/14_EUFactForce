from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from scoring.similarity import compute_fidelity_composite


@dataclass
class TaxonomyCounts:
    missing_content: int = 0
    extra_content: int = 0
    order_violation: int = 0
    fragmentation_issue: int = 0
    repeated_content: int = 0
    heading_section_drift: int = 0
    metadata_bleed: int = 0
    ambiguous_hunks: int = 0
    total_ref_sentences: int = 0
    total_ext_sentences: int = 0


def load_quality_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing quality scores file: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: str | None) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def round_opt(value: float | None, ndigits: int = 4) -> float | None:
    return round(value, ndigits) if value is not None else None


def derive_preprocess_profile(parser_config: str) -> str:
    if parser_config.endswith("_clean"):
        return "clean"
    if parser_config.endswith("_column"):
        return "column"
    return "default"


def derive_parser_family(parser_config: str) -> str:
    if parser_config.startswith("llamaparse"):
        return "llamaparse"
    if parser_config.startswith("pymupdf"):
        return "pymupdf"
    return "other"


def derive_postprocess_profile(parser_config: str) -> str:
    # Current benchmark defaults are all "default"; keep logic explicit for
    # future profile-based configs.
    if "policy" in parser_config:
        return "policy_report"
    return "default"


def ensure_fidelity_composite(rows: list[dict]) -> None:
    for row in rows:
        if to_float(row.get("fidelity_composite")) is not None:
            continue
        sim = to_float(row.get("text_similarity"))
        rec = to_float(row.get("content_recall"))
        prec = to_float(row.get("content_precision"))
        order = to_float(row.get("order_score"))
        if sim is None or rec is None or prec is None:
            row["fidelity_composite"] = ""
            continue
        row["fidelity_composite"] = str(
            compute_fidelity_composite(
                text_similarity=sim,
                content_recall=rec,
                content_precision=prec,
                order_score=order,
            )
        )


def group_rows(rows: list[dict], key_fields: tuple[str, ...]) -> dict[tuple[str, ...], list[dict]]:
    grouped: dict[tuple[str, ...], list[dict]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        grouped.setdefault(key, []).append(row)
    return grouped


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        # Keep deterministic empty CSV with no rows.
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

