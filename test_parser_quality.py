"""
Test parser quality against verified ground truth.

Runs Docling parser on all PDFs and compares with verified ground truth texts.
Computes: similarity, recall, precision, structural quality.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_pdf_with_docling(pdf_path: str) -> str:
    """Parse PDF using Docling."""
    try:
        from docling.document_converter import DocumentConverter
        from hierarchical.postprocessor import ResultPostprocessor
        from eu_fact_force.ingestion.parsing.docling_postprocess import (
            render_docling_output,
        )

        parser = DocumentConverter()
        result = parser.convert(pdf_path)
        ResultPostprocessor(result).process()
        doc_dict = result.document.export_to_dict()

        full_text, stats = render_docling_output(
            file_path=Path(pdf_path),
            result=result,
            doc_dict=doc_dict,
            result_type="markdown",
            validate_text_bboxes=True,
        )

        return full_text if full_text else ""

    except Exception as e:
        logger.error(f"Docling parsing failed for {pdf_path}: {e}")
        return ""


def compute_text_similarity(text1: str, text2: str, model=None) -> float:
    """Compute semantic similarity between two texts."""
    if not text1 or not text2:
        return 0.0

    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")

    try:
        # Normalize to reasonable length (max 1000 tokens)
        text1 = text1[:5000]
        text2 = text2[:5000]

        emb1 = model.encode([text1], convert_to_tensor=False, show_progress_bar=False)
        emb2 = model.encode([text2], convert_to_tensor=False, show_progress_bar=False)

        similarity = float(cosine_similarity([emb1[0]], [emb2[0]])[0][0])
        return max(0.0, min(1.0, similarity))

    except Exception as e:
        logger.error(f"Similarity computation failed: {e}")
        return 0.0


def compute_recall(extracted: str, ground_truth: str) -> float:
    """Compute recall: what fraction of ground truth is in extracted."""
    if not ground_truth:
        return 1.0 if not extracted else 0.0

    # Simple heuristic: common words/phrases
    extracted_words = set(extracted.lower().split())
    truth_words = set(ground_truth.lower().split())

    if not truth_words:
        return 1.0

    common = len(extracted_words & truth_words)
    recall = common / len(truth_words)
    return min(1.0, max(0.0, recall))


def compute_precision(extracted: str, ground_truth: str) -> float:
    """Compute precision: what fraction of extracted is in ground truth."""
    if not extracted:
        return 1.0 if not ground_truth else 0.0

    extracted_words = set(extracted.lower().split())
    truth_words = set(ground_truth.lower().split())

    if not extracted_words:
        return 1.0

    common = len(extracted_words & truth_words)
    precision = common / len(extracted_words)
    return min(1.0, max(0.0, precision))


def compute_structural_quality(extracted: str) -> float:
    """Measure structural quality (fragmentation, orphan lines, etc)."""
    if not extracted:
        return 0.0

    lines = extracted.split("\n")
    total_lines = len(lines)

    if total_lines == 0:
        return 0.0

    # Count problematic patterns
    orphan_lines = 0  # Very short lines
    fragmented_lines = 0  # Lines ending with hyphen

    for line in lines:
        stripped = line.strip()
        if len(stripped) > 0 and len(stripped) < 20:
            orphan_lines += 1
        if stripped.endswith("-") and len(stripped) > 5:
            fragmented_lines += 1

    issues = orphan_lines + fragmented_lines
    quality_score = max(0.0, 1.0 - (issues / max(1, total_lines)))

    return quality_score


class ParserQualityTester:
    """Test parser quality against verified ground truth."""

    def __init__(
        self,
        pdf_dir: str = "verified_ground_truth_data/pdf",
        text_dir: str = "verified_ground_truth_data/text",
        output_file: str = "parser_quality_report.json",
    ):
        self.pdf_dir = Path(pdf_dir)
        self.text_dir = Path(text_dir)
        self.output_file = Path(output_file)
        self.model = None  # Lazy load
        self.results = []

    def test_all(self):
        """Test parser on all PDFs."""
        if not self.pdf_dir.exists():
            logger.error(f"PDF directory not found: {self.pdf_dir}")
            return

        pdf_files = sorted(self.pdf_dir.glob("*.pdf"))
        logger.info(f"Testing {len(pdf_files)} PDFs...")
        logger.info(f"Ground truth directory: {self.text_dir}")
        logger.info("")

        for i, pdf_path in enumerate(pdf_files, 1):
            article_id = pdf_path.stem
            logger.info(f"[{i}/{len(pdf_files)}] {article_id}")

            # Parse PDF
            logger.info("  Parsing PDF with Docling...")
            start_time = time.time()
            extracted_text = parse_pdf_with_docling(str(pdf_path))
            parse_time = time.time() - start_time
            logger.info(f"    Extracted {len(extracted_text):,} chars in {parse_time:.2f}s")

            # Load ground truth
            text_path = self.text_dir / f"{article_id}.txt"
            if not text_path.exists():
                logger.warning(f"    No ground truth for {article_id}")
                self.results.append(
                    {
                        "article_id": article_id,
                        "has_ground_truth": False,
                        "extracted_chars": len(extracted_text),
                        "parse_time_s": parse_time,
                    }
                )
                continue

            ground_truth = text_path.read_text(encoding="utf-8", errors="ignore")
            logger.info(f"    Ground truth: {len(ground_truth):,} chars")

            # Compute metrics
            logger.info("  Computing metrics...")
            similarity = compute_text_similarity(extracted_text, ground_truth, self.model)
            recall = compute_recall(extracted_text, ground_truth)
            precision = compute_precision(extracted_text, ground_truth)
            structure = compute_structural_quality(extracted_text)

            logger.info(f"    Similarity:  {similarity:.1%}")
            logger.info(f"    Recall:      {recall:.1%}")
            logger.info(f"    Precision:   {precision:.1%}")
            logger.info(f"    Structure:   {structure:.1%}")

            self.results.append(
                {
                    "article_id": article_id,
                    "has_ground_truth": True,
                    "extracted_chars": len(extracted_text),
                    "ground_truth_chars": len(ground_truth),
                    "parse_time_s": parse_time,
                    "similarity": float(similarity),
                    "recall": float(recall),
                    "precision": float(precision),
                    "structural_quality": float(structure),
                }
            )

        self.generate_report()

    def generate_report(self):
        """Generate quality report."""
        logger.info("\n" + "=" * 60)
        logger.info("PARSER QUALITY REPORT")
        logger.info("=" * 60)

        with_gt = [r for r in self.results if r.get("has_ground_truth")]
        without_gt = [r for r in self.results if not r.get("has_ground_truth")]

        logger.info(f"\nSummary:")
        logger.info(f"  Total PDFs tested:        {len(self.results)}")
        logger.info(f"  With ground truth:        {len(with_gt)}")
        logger.info(f"  Without ground truth:     {len(without_gt)}")

        if with_gt:
            logger.info(f"\nQuality Metrics (n={len(with_gt)}):")

            similarity_avg = sum(r["similarity"] for r in with_gt) / len(with_gt)
            recall_avg = sum(r["recall"] for r in with_gt) / len(with_gt)
            precision_avg = sum(r["precision"] for r in with_gt) / len(with_gt)
            structure_avg = sum(r["structural_quality"] for r in with_gt) / len(with_gt)
            parse_time_avg = sum(r["parse_time_s"] for r in with_gt) / len(with_gt)

            logger.info(f"  Similarity:    {similarity_avg:.1%} ± {self._std([r['similarity'] for r in with_gt]):.1%}")
            logger.info(f"  Recall:        {recall_avg:.1%} ± {self._std([r['recall'] for r in with_gt]):.1%}")
            logger.info(f"  Precision:     {precision_avg:.1%} ± {self._std([r['precision'] for r in with_gt]):.1%}")
            logger.info(f"  Structure:     {structure_avg:.1%} ± {self._std([r['structural_quality'] for r in with_gt]):.1%}")
            logger.info(f"  Parse time:    {parse_time_avg:.2f}s avg")

            logger.info(f"\nTop performers (by similarity):")
            top = sorted(with_gt, key=lambda r: r["similarity"], reverse=True)[:5]
            for r in top:
                logger.info(
                    f"  {r['article_id']}: {r['similarity']:.1%} "
                    f"(recall={r['recall']:.1%}, precision={r['precision']:.1%})"
                )

            logger.info(f"\nBottom performers (by similarity):")
            bottom = sorted(with_gt, key=lambda r: r["similarity"])[:5]
            for r in bottom:
                logger.info(
                    f"  {r['article_id']}: {r['similarity']:.1%} "
                    f"(recall={r['recall']:.1%}, precision={r['precision']:.1%})"
                )

        # Save report
        report = {
            "summary": {
                "total_pdfs": len(self.results),
                "with_ground_truth": len(with_gt),
                "without_ground_truth": len(without_gt),
            },
            "metrics": {
                "similarity_avg": float(sum(r.get("similarity", 0) for r in with_gt) / len(with_gt)) if with_gt else 0,
                "recall_avg": float(sum(r.get("recall", 0) for r in with_gt) / len(with_gt)) if with_gt else 0,
                "precision_avg": float(sum(r.get("precision", 0) for r in with_gt) / len(with_gt)) if with_gt else 0,
                "structural_quality_avg": float(sum(r.get("structural_quality", 0) for r in with_gt) / len(with_gt)) if with_gt else 0,
            },
            "results": self.results,
        }

        self.output_file.write_text(json.dumps(report, indent=2))
        logger.info(f"\n✓ Report saved to {self.output_file}")

    @staticmethod
    def _std(values):
        """Compute standard deviation."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test parser quality")
    parser.add_argument("--pdf-dir", default="verified_ground_truth_data/pdf")
    parser.add_argument("--text-dir", default="verified_ground_truth_data/text")
    parser.add_argument("--output", default="parser_quality_report.json")

    args = parser.parse_args()

    tester = ParserQualityTester(
        pdf_dir=args.pdf_dir,
        text_dir=args.text_dir,
        output_file=args.output,
    )
    tester.test_all()
