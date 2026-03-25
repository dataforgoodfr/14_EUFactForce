"""
Metadata accuracy scoring.

Compares extracted text against ground truth to evaluate how accurately
the parser preserves document metadata (title, authors, DOI, date,
source, abstract, keywords).
"""

import re

from .utils import contains_fuzzy, METADATA_SEARCH_CHARS

# Fuzzy threshold for author and keyword matching
FUZZY_MATCH_THRESHOLD = 0.70

# Year is always the first 4 characters of a date string (e.g. "2023-05-14")
YEAR_LENGTH = 4

# Metadata accuracy weights (among applicable fields).
# Fields with None are excluded and weights redistributed proportionally.
_ACCURACY_WEIGHTS: dict[str, int] = {
    "title": 20,
    "authors": 20,
    "doi": 15,
    "date": 10,
    "source": 10,
    "abstract": 15,
    "keywords": 10,
}


def _normalize_keywords(raw: str) -> set[str]:
    """
    Normalise a keyword string by splitting on common separators
    (comma, pipe, semicolon) and returning a set of lowercased,
    trimmed tokens.
    """
    tokens = re.split(r"[,|;]", raw)
    return {t.strip().lower() for t in tokens if t.strip()}


def score_title_accuracy(full_text: str, expected_title: str) -> float:
    """
    Return the best fuzzy-match ratio of the expected title against
    the extracted text (sliding window in the first N chars).
    """
    _, ratio = contains_fuzzy(full_text[:METADATA_SEARCH_CHARS], expected_title, threshold=0.0)
    return round(ratio, 4)


def score_authors_accuracy(
    full_text: str,
    expected_authors: list[str],
) -> tuple[float, float]:
    """
    Compute recall of author names found in the first N chars.

    Returns (recall, avg_ratio).
      - recall:    fraction of expected authors found (fuzzy >= threshold)
      - avg_ratio: average best-match ratio across all authors
    """
    snippet = full_text[:METADATA_SEARCH_CHARS]
    found_count = 0
    ratios = []
    for author in expected_authors:
        ok, ratio = contains_fuzzy(snippet, author, threshold=FUZZY_MATCH_THRESHOLD)
        ratios.append(ratio)
        if ok:
            found_count += 1

    recall = round(found_count / len(expected_authors), 4) if expected_authors else 0.0
    avg_ratio = round(sum(ratios) / len(ratios), 4) if ratios else 0.0
    return recall, avg_ratio


def score_doi_accuracy(full_text: str, expected_doi: str | None) -> float | None:
    """
    Check if the exact expected DOI string appears in the text.
    Returns 1.0 (exact match), 0.0 (not found), or None (no DOI expected).
    """
    if expected_doi is None:
        return None
    return 1.0 if expected_doi in full_text else 0.0


def score_date_accuracy(full_text: str, expected_date: str | None) -> float | None:
    """
    Check if the publication year appears in the first N chars.
    Returns 1.0 (year found), 0.0 (year not found), or None if no date.
    """
    if not expected_date:
        return None
    year = expected_date[:YEAR_LENGTH]
    return 1.0 if year in full_text[:METADATA_SEARCH_CHARS] else 0.0


def score_source_accuracy(full_text: str, expected_source: str | None) -> float | None:
    """
    Check if the journal/source name appears in the first N chars.
    Uses fuzzy matching to handle minor formatting differences.
    Returns the best match ratio, or None if no source expected.
    """
    if not expected_source:
        return None
    _, ratio = contains_fuzzy(full_text[:METADATA_SEARCH_CHARS], expected_source, threshold=0.0)
    return round(ratio, 4)


def score_abstract_accuracy(
    full_text: str,
    expected_first_sentence: str | None,
) -> float | None:
    """
    Check if the expected first sentence appears in the extracted text.
    Returns the best match ratio, or None if no abstract expected.
    """
    if not expected_first_sentence:
        return None
    _, ratio = contains_fuzzy(full_text, expected_first_sentence, threshold=0.0)
    return round(ratio, 4)


def score_keywords_accuracy(
    full_text: str,
    expected_keywords: str | None,
) -> tuple[float | None, float | None]:
    """
    Check keyword extraction accuracy by measuring what fraction of
    expected keywords appear in the extracted text.

    Returns (keyword_recall, keyword_avg_ratio) or (None, None).
    """
    if not expected_keywords:
        return None, None

    expected_set = _normalize_keywords(expected_keywords)
    if not expected_set:
        return None, None

    text_lower = full_text.lower()
    found_count = 0
    ratios = []
    for kw in expected_set:
        if kw in text_lower:
            found_count += 1
            ratios.append(1.0)
        else:
            _, ratio = contains_fuzzy(full_text, kw, threshold=0.0)
            ratios.append(ratio)
            if ratio >= FUZZY_MATCH_THRESHOLD:
                found_count += 1

    recall = round(found_count / len(expected_set), 4)
    avg_ratio = round(sum(ratios) / len(ratios), 4) if ratios else 0.0
    return recall, avg_ratio


def compute_metadata_accuracy_score(
    title_acc: float,
    authors_recall: float,
    doi_acc: float | None,
    date_acc: float | None,
    source_acc: float | None,
    abstract_acc: float | None,
    keyword_recall: float | None,
) -> float:
    """
    Combine metadata accuracy metrics into a single 0-100 score.

    Fields with None are excluded and weights redistributed proportionally.
    """
    values = {
        "title": title_acc,
        "authors": authors_recall,
        "doi": doi_acc,
        "date": date_acc,
        "source": source_acc,
        "abstract": abstract_acc,
        "keywords": keyword_recall,
    }

    total_weight = 0
    weighted_sum = 0.0
    for name, value in values.items():
        if value is not None:
            weight = _ACCURACY_WEIGHTS[name]
            total_weight += weight
            weighted_sum += value * weight

    if total_weight == 0:
        return 0.0
    return round((weighted_sum / total_weight) * 100, 1)
