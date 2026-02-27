from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from fidelity.common import (
    TaxonomyCounts,
    avg,
    derive_parser_family,
    derive_postprocess_profile,
    derive_preprocess_profile,
    group_rows,
    round_opt,
    write_csv,
)
from fidelity.constants import (
    AMBIGUOUS_MATCH_LOWER_BOUND,
    EARLY_MATCH_BREAK_THRESHOLD,
    FRAGMENT_SHORT_LINE_MAX_CHARS,
    FRAGMENT_SHORT_LINE_MAX_WORDS,
    LENGTH_MISMATCH_RATIO,
    MIN_SENTENCE_LEN,
    REPEATED_PARAGRAPH_MIN_CHARS,
    SENTENCE_MATCH_THRESHOLD,
)
from scoring.utils import normalize_for_similarity, split_sentences, strip_references_section


def _normalize_body(text: str) -> str:
    return normalize_for_similarity(strip_references_section(text))


def _sentence_best_match(
    sentence: str,
    corpus: list[str],
    corpus_index_map: dict[str, int],
    length_mismatch_ratio: float = LENGTH_MISMATCH_RATIO,
) -> tuple[float, int]:
    exact_idx = corpus_index_map.get(sentence)
    if exact_idx is not None:
        return 1.0, exact_idx

    best_ratio = 0.0
    best_idx = -1
    sentence_len = len(sentence)
    for i, other in enumerate(corpus):
        if abs(sentence_len - len(other)) > sentence_len * length_mismatch_ratio:
            continue
        ratio = SequenceMatcher(None, sentence, other).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i
        if best_ratio >= EARLY_MATCH_BREAK_THRESHOLD:
            break
    return best_ratio, best_idx


def _count_fragmented_lines(text: str) -> int:
    lines = text.splitlines()
    count = 0
    for i, line in enumerate(lines[:-1]):
        s = line.strip()
        if not s:
            continue
        nxt = lines[i + 1].strip()
        if s.endswith("-") and nxt and nxt[0].islower():
            count += 1
        if (
            len(s.split()) <= FRAGMENT_SHORT_LINE_MAX_WORDS
            and len(s) <= FRAGMENT_SHORT_LINE_MAX_CHARS
            and not s.startswith("#")
        ):
            count += 1
    return count


def _count_repeated_paragraphs(text: str) -> int:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    normed = [
        re.sub(r"\s+", " ", p).lower()
        for p in paras
        if len(p) >= REPEATED_PARAGRAPH_MIN_CHARS
    ]
    counts: dict[str, int] = {}
    for p in normed:
        counts[p] = counts.get(p, 0) + 1
    return sum(v - 1 for v in counts.values() if v > 1)


def _count_heading_drift(extracted_text: str, sections_in_order: list[str] | None) -> int:
    if not sections_in_order:
        return 0
    found = [m.group(1).strip().lower() for m in re.finditer(r"^#{1,3}\s+(.+)$", extracted_text, flags=re.MULTILINE)]
    if not found:
        return len(sections_in_order)
    missing = 0
    for expected in sections_in_order:
        e = expected.lower()
        if not any(e in h or h in e for h in found):
            missing += 1
    return missing


def _count_metadata_bleed(extracted_text: str, title: str, authors: list[str]) -> int:
    body = extracted_text
    bleed = 0
    if title:
        occurrences = body.lower().count(title.lower())
        if occurrences > 1:
            bleed += occurrences - 1
    for author in authors or []:
        occurrences = body.lower().count(author.lower())
        if occurrences > 1:
            bleed += occurrences - 1
    return bleed


def _taxonomy_for_pair(
    extracted_text: str,
    reference_text: str,
    gt_entry: dict,
) -> TaxonomyCounts:
    counts = TaxonomyCounts()
    ext_sentences = [s for s in split_sentences(_normalize_body(extracted_text)) if len(s) >= MIN_SENTENCE_LEN]
    ref_sentences = [s for s in split_sentences(_normalize_body(reference_text)) if len(s) >= MIN_SENTENCE_LEN]
    counts.total_ext_sentences = len(ext_sentences)
    counts.total_ref_sentences = len(ref_sentences)
    ext_index_map = {s: i for i, s in enumerate(ext_sentences)}
    ref_index_map = {s: i for i, s in enumerate(ref_sentences)}

    matched_positions: list[int] = []
    for ref_sentence in ref_sentences:
        ratio, idx = _sentence_best_match(ref_sentence, ext_sentences, ext_index_map)
        if ratio >= SENTENCE_MATCH_THRESHOLD and idx >= 0:
            matched_positions.append(idx)
        else:
            counts.missing_content += 1

    for ext_sentence in ext_sentences:
        ratio, _ = _sentence_best_match(ext_sentence, ref_sentences, ref_index_map)
        if ratio < SENTENCE_MATCH_THRESHOLD:
            counts.extra_content += 1
            if AMBIGUOUS_MATCH_LOWER_BOUND <= ratio < SENTENCE_MATCH_THRESHOLD:
                counts.ambiguous_hunks += 1

    if matched_positions:
        for i in range(1, len(matched_positions)):
            if matched_positions[i] < matched_positions[i - 1]:
                counts.order_violation += 1

    counts.fragmentation_issue = _count_fragmented_lines(extracted_text)
    counts.repeated_content = _count_repeated_paragraphs(extracted_text)
    counts.heading_section_drift = _count_heading_drift(
        extracted_text=extracted_text,
        sections_in_order=gt_entry.get("sections_in_order"),
    )
    counts.metadata_bleed = _count_metadata_bleed(
        extracted_text=extracted_text,
        title=gt_entry.get("title", ""),
        authors=gt_entry.get("authors", []),
    )
    return counts


def command_taxonomy(args: argparse.Namespace) -> None:
    print(f"[INFO] Loading ground truth from {args.ground_truth_json}", flush=True)
    gt = json.loads(Path(args.ground_truth_json).read_text(encoding="utf-8"))
    docs = gt["documents"]
    print(f"[INFO] Ground truth documents: {len(docs)}", flush=True)

    taxonomy_rows: list[dict] = []
    total_pairs = 0
    for filename in docs:
        stem = Path(filename).stem
        total_pairs += len(list(Path(args.extracted_text_dir).glob(f"{stem}__*.txt")))
    print(f"[INFO] Candidate (doc, config) pairs: {total_pairs}", flush=True)

    processed_pairs = 0
    for filename, entry in docs.items():
        ref_path = _find_reference_text(filename, Path(args.ground_truth_text_dir))
        if ref_path is None:
            print(f"[SKIP] No reference text for {filename}", flush=True)
            continue
        reference_text = ref_path.read_text(encoding="utf-8")
        stem = Path(filename).stem
        print(f"[DOC] Taxonomy on {filename}", flush=True)
        for text_file in sorted(Path(args.extracted_text_dir).glob(f"{stem}__*.txt")):
            parser_config = text_file.stem.split("__", 1)[1]
            print(f"[PAIR] {filename} | {parser_config}", flush=True)
            extracted_text = text_file.read_text(encoding="utf-8")
            counts = _taxonomy_for_pair(
                extracted_text=extracted_text,
                reference_text=reference_text,
                gt_entry=entry,
            )
            taxonomy_rows.append(
                {
                    "filename": filename,
                    "doc_type": entry.get("doc_type", ""),
                    "parser_config": parser_config,
                    "parser_family": derive_parser_family(parser_config),
                    "preprocess_profile": derive_preprocess_profile(parser_config),
                    "postprocess_profile": derive_postprocess_profile(parser_config),
                    "missing_content": counts.missing_content,
                    "extra_content": counts.extra_content,
                    "order_violation": counts.order_violation,
                    "fragmentation_issue": counts.fragmentation_issue,
                    "repeated_content": counts.repeated_content,
                    "heading_section_drift": counts.heading_section_drift,
                    "metadata_bleed": counts.metadata_bleed,
                    "ambiguous_hunks": counts.ambiguous_hunks,
                    "total_ref_sentences": counts.total_ref_sentences,
                    "total_ext_sentences": counts.total_ext_sentences,
                }
            )
            processed_pairs += 1
            if processed_pairs % max(1, args.progress_every) == 0:
                print(
                    f"[PROGRESS] taxonomy {processed_pairs}/{total_pairs} pairs processed",
                    flush=True,
                )

    write_csv(Path(args.output_csv), taxonomy_rows)

    grouped = group_rows(taxonomy_rows, ("parser_config",))
    summary_rows = []
    for (parser_config,), grp in grouped.items():
        summary_rows.append(
            {
                "parser_config": parser_config,
                "num_documents": len(grp),
                "missing_content_avg": round_opt(avg([float(r["missing_content"]) for r in grp]), 2),
                "extra_content_avg": round_opt(avg([float(r["extra_content"]) for r in grp]), 2),
                "order_violation_avg": round_opt(avg([float(r["order_violation"]) for r in grp]), 2),
                "fragmentation_issue_avg": round_opt(avg([float(r["fragmentation_issue"]) for r in grp]), 2),
                "repeated_content_avg": round_opt(avg([float(r["repeated_content"]) for r in grp]), 2),
                "heading_section_drift_avg": round_opt(avg([float(r["heading_section_drift"]) for r in grp]), 2),
                "metadata_bleed_avg": round_opt(avg([float(r["metadata_bleed"]) for r in grp]), 2),
            }
        )
    summary_rows.sort(key=lambda r: (r["missing_content_avg"] or 9999, r["extra_content_avg"] or 9999))
    write_csv(Path(args.output_summary_csv), summary_rows)
    print(f"[OK] Taxonomy rows written to {args.output_csv}")
    print(f"[OK] Taxonomy summary written to {args.output_summary_csv}")


def _find_reference_text(filename: str, ground_truth_text_dir: Path) -> Path | None:
    stem = Path(filename).stem
    for ext in (".md", ".txt"):
        candidate = ground_truth_text_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None

