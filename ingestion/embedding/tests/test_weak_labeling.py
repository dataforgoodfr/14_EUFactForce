import copy
import json

import pytest

from ingestion.embedding import benchmark_runner
from ingestion.embedding.weak_labeling_calibration import build_calibration_report
from ingestion.embedding.weak_labeling import generate_weak_labels_data
from ingestion.embedding.weak_labeling_io import run_weak_label_generation


def _sample_docs() -> dict[str, str]:
    return {
        "doc_a": (
            "Vaccines reduce severe disease in populations.\n\n"
            "Misinformation can lower uptake and increase preventable harm."
        ),
        "doc_b": (
            "Influencer marketing can hide sponsorship disclosures.\n\n"
            "Health claims in sponsored content should be verified."
        ),
    }


def _sample_ground_truth() -> list[dict]:
    return [
        {
            "query": "vaccine misinformation harms public health",
            "lang": "en",
            "relevant_docs": ["doc_a"],
            "relevant_chunk_ids_by_strategy": {
                "char": ["doc_a::chunk_0"],
                "paragraph": ["doc_a::chunk_0"],
            },
        },
        {
            "query": "influencer health claims disclosure",
            "lang": "en",
            "relevant_docs": ["doc_b"],
            "relevant_chunk_ids_by_strategy": {
                "char": ["doc_b::chunk_0"],
                "paragraph": ["doc_b::chunk_0"],
            },
        },
    ]


def _sample_key_passages() -> dict[str, str]:
    return {
        "doc_a": "Misinformation can lower uptake and increase preventable harm.",
        "doc_b": "Health claims in sponsored content should be verified.",
    }


def test_weak_label_schema_fields_present():
    out = generate_weak_labels_data(
        ground_truth=copy.deepcopy(_sample_ground_truth()),
        docs=_sample_docs(),
        strategies=("char",),
        random_seed=7,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    for row in out:
        assert "weak_chunk_labels_by_strategy" in row
        assert "char" in row["weak_chunk_labels_by_strategy"]
        labels = row["weak_chunk_labels_by_strategy"]["char"]
        assert labels
        first = labels[0]
        assert {"chunk_id", "label", "confidence", "sources"} <= set(first.keys())
        assert isinstance(first["sources"], list)


def test_weak_label_generation_is_deterministic_with_seed():
    a = generate_weak_labels_data(
        ground_truth=copy.deepcopy(_sample_ground_truth()),
        docs=_sample_docs(),
        strategies=("char", "paragraph"),
        random_seed=13,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    b = generate_weak_labels_data(
        ground_truth=copy.deepcopy(_sample_ground_truth()),
        docs=_sample_docs(),
        strategies=("char", "paragraph"),
        random_seed=13,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    assert a == b


def test_cross_strategy_outputs_exist():
    out = generate_weak_labels_data(
        ground_truth=copy.deepcopy(_sample_ground_truth()),
        docs=_sample_docs(),
        strategies=("char", "paragraph"),
        random_seed=9,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    for row in out:
        weak_by = row["weak_chunk_labels_by_strategy"]
        assert "char" in weak_by and "paragraph" in weak_by
        assert isinstance(weak_by["char"], list)
        assert isinstance(weak_by["paragraph"], list)


def test_anchor_queries_produce_positive_labels():
    out = generate_weak_labels_data(
        ground_truth=copy.deepcopy(_sample_ground_truth()),
        docs=_sample_docs(),
        strategies=("char",),
        random_seed=21,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    for row in out:
        positives = [
            item
            for item in row["weak_chunk_labels_by_strategy"]["char"]
            if item["label"] in ("high", "partial")
        ]
        assert positives, f"Expected at least one positive weak label for query: {row['query']}"


def test_manual_chunk_ids_are_not_overwritten_by_weak_labels():
    source = copy.deepcopy(_sample_ground_truth())
    out = generate_weak_labels_data(
        ground_truth=source,
        docs=_sample_docs(),
        strategies=("char",),
        random_seed=21,
        key_passages=_sample_key_passages(),
        use_dense=False,
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    for idx, row in enumerate(out):
        assert row["relevant_chunk_ids_by_strategy"]["char"] == source[idx][
            "relevant_chunk_ids_by_strategy"
        ]["char"]


def test_calibration_uses_manual_labels_as_reference():
    ground_truth = [
        {
            "query": "q1",
            "lang": "en",
            "relevant_docs": ["doc_a"],
            "relevant_chunk_labels_by_strategy": {
                "char": [{"chunk_id": "doc_a::chunk_0", "label": "high"}]
            },
            "weak_chunk_labels_by_strategy": {
                "char": [
                    {
                        "chunk_id": "doc_a::chunk_0",
                        "label": "high",
                        "confidence": 0.9,
                        "sources": ["anchor_hit"],
                    },
                    {
                        "chunk_id": "doc_b::chunk_0",
                        "label": "partial",
                        "confidence": 0.5,
                        "sources": ["negative_sample"],
                    },
                ]
            },
        }
    ]
    report = build_calibration_report(ground_truth, strategies=("char",))
    row = report["strategies"]["char"]
    assert row["evaluated_queries_with_manual_labels"] == 1
    assert row["macro_precision"] == 0.5
    assert row["macro_recall"] == 1.0


def test_run_cli_forwards_suffix_flag(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_run_benchmark(strategy: str, multi_run: bool = False) -> None:
        captured["strategy"] = strategy
        captured["multi_run"] = multi_run

    monkeypatch.setattr(
        benchmark_runner,
        "run_benchmark",
        _fake_run_benchmark,
    )
    benchmark_runner.run_cli(
        benchmark_runner.argparse.Namespace(
            chunking_strategy="char",
            generate_weak_labels=False,
            weak_label_strategy="char",
            write_output="unused.json",
            suffix_by_strategy=True,
        )
    )
    assert captured == {"strategy": "char", "multi_run": True}


def test_weak_label_generation_validates_ground_truth_schema(tmp_path):
    bad_path = tmp_path / "bad_ground_truth.json"
    bad_path.write_text(json.dumps([{"query": "q1", "lang": "en"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="missing keys"):
        run_weak_label_generation(
            input_path=bad_path,
            output_path=tmp_path / "out.json",
            strategy_mode="char",
        )
