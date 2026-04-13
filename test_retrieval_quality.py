"""
Test retrieval quality against verified ground truth documents.

Measures how well the embedding-based search system finds relevant documents.
Computes standard IR metrics: recall@k, MRR, NDCG.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
import numpy as np

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def extract_key_passages(text: str, num_passages: int = 5) -> list[str]:
    """Extract key passages from text (non-empty paragraphs)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # Take first num_passages paragraphs as queries
    return paragraphs[:num_passages]


def compute_embeddings(texts: list[str], model=None) -> np.ndarray:
    """Compute embeddings for a list of texts."""
    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")

    embeddings = model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
    return np.array(embeddings)


def compute_recall_at_k(relevant_docs: set, retrieved_indices: list, k: int) -> float:
    """Compute recall@k: fraction of relevant docs found in top-k results."""
    if not relevant_docs:
        return 1.0

    found = len(relevant_docs & set(retrieved_indices[:k]))
    return found / len(relevant_docs)


def compute_precision_at_k(relevant_docs: set, retrieved_indices: list, k: int) -> float:
    """Compute precision@k: fraction of top-k results that are relevant."""
    if k == 0:
        return 0.0

    found = len(relevant_docs & set(retrieved_indices[:k]))
    return found / k


def compute_mrr(relevant_docs: set, retrieved_indices: list) -> float:
    """Compute Mean Reciprocal Rank: 1 / (rank of first relevant doc)."""
    for rank, doc_idx in enumerate(retrieved_indices, 1):
        if doc_idx in relevant_docs:
            return 1.0 / rank
    return 0.0


def compute_ndcg(relevant_docs: set, retrieved_indices: list, k: int) -> float:
    """
    Compute NDCG@k: Normalized Discounted Cumulative Gain.
    Rewards finding relevant docs early in ranking.
    """
    # DCG: sum of (relevance / log2(rank+1))
    dcg = 0.0
    for rank, doc_idx in enumerate(retrieved_indices[:k], 1):
        if doc_idx in relevant_docs:
            dcg += 1.0 / np.log2(rank + 1)

    # IDCG: DCG of ideal ranking (all relevant docs first)
    ideal_relevant = min(len(relevant_docs), k)
    idcg = sum(1.0 / np.log2(rank + 1) for rank in range(1, ideal_relevant + 1))

    if idcg == 0:
        return 1.0 if len(relevant_docs) == 0 else 0.0

    return dcg / idcg


class RetrieverQualityTester:
    """Test retrieval quality against verified ground truth documents."""

    def __init__(
        self,
        pdf_dir: str = "verified_ground_truth_data/pdf",
        text_dir: str = "verified_ground_truth_data/text",
        output_file: str = "retrieval_quality_report.json",
    ):
        self.pdf_dir = Path(pdf_dir)
        self.text_dir = Path(text_dir)
        self.output_file = Path(output_file)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.results = []

        # Load all ground truth documents
        self.documents = {}
        self.doc_embeddings = None
        self.doc_ids_to_indices = {}
        self._load_documents()

    def _load_documents(self):
        """Load all ground truth text documents."""
        logger.info("Loading ground truth documents...")

        text_files = sorted(self.text_dir.glob("*.txt"))
        doc_texts = []

        for i, text_path in enumerate(text_files):
            article_id = text_path.stem
            try:
                text = text_path.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    self.documents[article_id] = {
                        "text": text,
                        "path": str(text_path),
                    }
                    doc_texts.append(text[:5000])  # Limit to first 5000 chars for embedding
                    self.doc_ids_to_indices[article_id] = len(doc_texts) - 1
            except Exception as e:
                logger.warning(f"Failed to load {article_id}: {e}")

        logger.info(f"Loaded {len(self.documents)} documents")

        # Compute embeddings for all documents
        if doc_texts:
            logger.info("Computing document embeddings...")
            self.doc_embeddings = compute_embeddings(doc_texts, self.model)

    def retrieve_similar(self, query_text: str, k: int = 10) -> list[tuple[str, float]]:
        """
        Retrieve top-k documents similar to query.
        Returns list of (article_id, similarity_score) tuples.
        """
        if not self.documents or self.doc_embeddings is None:
            return []

        # Embed query
        query_emb = compute_embeddings([query_text[:5000]], self.model)

        # Compute similarities to all documents
        similarities = cosine_similarity(query_emb, self.doc_embeddings)[0]

        # Get top-k
        top_indices = np.argsort(-similarities)[:k]

        # Convert back to article IDs
        index_to_id = {v: k for k, v in self.doc_ids_to_indices.items()}
        results = [
            (index_to_id[idx], float(similarities[idx]))
            for idx in top_indices
            if idx in index_to_id
        ]

        return results

    def test_all(self):
        """Test retrieval for each document."""
        logger.info(f"\nTesting retrieval for {len(self.documents)} documents...")
        logger.info("")

        for i, (article_id, doc_info) in enumerate(self.documents.items(), 1):
            logger.info(f"[{i}/{len(self.documents)}] {article_id}")

            text = doc_info["text"]

            # Extract 5 key passages as queries
            passages = extract_key_passages(text, num_passages=5)

            if not passages:
                logger.warning(f"  No passages found for {article_id}")
                self.results.append({
                    "article_id": article_id,
                    "num_passages": 0,
                    "metrics": None,
                })
                continue

            logger.info(f"  Extracted {len(passages)} passages as queries")

            # For each passage, retrieve documents and measure metrics
            passage_metrics = []

            for p_idx, passage in enumerate(passages, 1):
                if len(passage) < 20:  # Skip very short passages
                    continue

                # Retrieve top-20 documents
                retrieved = self.retrieve_similar(passage, k=20)
                retrieved_ids = [doc_id for doc_id, _ in retrieved]

                # The relevant document is the original article itself
                # Additionally, similar articles are bonus relevant docs
                relevant = {article_id}  # At minimum, must find itself

                # Compute metrics
                recall_5 = compute_recall_at_k(relevant, retrieved_ids, 5)
                recall_10 = compute_recall_at_k(relevant, retrieved_ids, 10)
                recall_20 = compute_recall_at_k(relevant, retrieved_ids, 20)

                precision_5 = compute_precision_at_k(relevant, retrieved_ids, 5)
                precision_10 = compute_precision_at_k(relevant, retrieved_ids, 10)

                mrr = compute_mrr(relevant, retrieved_ids)
                ndcg_10 = compute_ndcg(relevant, retrieved_ids, 10)

                # Log if document was found
                found_rank = None
                if article_id in retrieved_ids:
                    found_rank = retrieved_ids.index(article_id) + 1

                passage_metrics.append({
                    "passage_idx": p_idx,
                    "query_length": len(passage),
                    "found_rank": found_rank,
                    "recall@5": float(recall_5),
                    "recall@10": float(recall_10),
                    "recall@20": float(recall_20),
                    "precision@5": float(precision_5),
                    "precision@10": float(precision_10),
                    "mrr": float(mrr),
                    "ndcg@10": float(ndcg_10),
                })

            # Aggregate metrics across passages
            if passage_metrics:
                avg_recall_10 = np.mean([m["recall@10"] for m in passage_metrics])
                avg_mrr = np.mean([m["mrr"] for m in passage_metrics])
                avg_ndcg = np.mean([m["ndcg@10"] for m in passage_metrics])

                logger.info(f"    Avg Recall@10: {avg_recall_10:.1%}")
                logger.info(f"    Avg MRR:       {avg_mrr:.1%}")
                logger.info(f"    Avg NDCG@10:   {avg_ndcg:.1%}")

                self.results.append({
                    "article_id": article_id,
                    "num_passages": len(passage_metrics),
                    "metrics": {
                        "recall@5_avg": float(np.mean([m["recall@5"] for m in passage_metrics])),
                        "recall@10_avg": float(np.mean([m["recall@10"] for m in passage_metrics])),
                        "recall@20_avg": float(np.mean([m["recall@20"] for m in passage_metrics])),
                        "precision@5_avg": float(np.mean([m["precision@5"] for m in passage_metrics])),
                        "precision@10_avg": float(np.mean([m["precision@10"] for m in passage_metrics])),
                        "mrr_avg": avg_mrr,
                        "ndcg@10_avg": avg_ndcg,
                    },
                    "passage_details": passage_metrics,
                })

        self.generate_report()

    def generate_report(self):
        """Generate retrieval quality report."""
        logger.info("\n" + "=" * 60)
        logger.info("RETRIEVAL QUALITY REPORT")
        logger.info("=" * 60)

        logger.info(f"\nSummary:")
        logger.info(f"  Total documents tested:  {len(self.results)}")

        with_metrics = [r for r in self.results if r.get("metrics")]
        logger.info(f"  With retrieval metrics:  {len(with_metrics)}")

        if with_metrics:
            logger.info(f"\nRetrieval Metrics (n={len(with_metrics)}):")

            recall_10_avg = np.mean([r["metrics"]["recall@10_avg"] for r in with_metrics])
            recall_20_avg = np.mean([r["metrics"]["recall@20_avg"] for r in with_metrics])
            mrr_avg = np.mean([r["metrics"]["mrr_avg"] for r in with_metrics])
            ndcg_avg = np.mean([r["metrics"]["ndcg@10_avg"] for r in with_metrics])

            logger.info(f"  Recall@10:     {recall_10_avg:.1%} ± {self._std([r['metrics']['recall@10_avg'] for r in with_metrics]):.1%}")
            logger.info(f"  Recall@20:     {recall_20_avg:.1%} ± {self._std([r['metrics']['recall@20_avg'] for r in with_metrics]):.1%}")
            logger.info(f"  MRR (rank):    {mrr_avg:.1%} ± {self._std([r['metrics']['mrr_avg'] for r in with_metrics]):.1%}")
            logger.info(f"  NDCG@10:       {ndcg_avg:.1%} ± {self._std([r['metrics']['ndcg@10_avg'] for r in with_metrics]):.1%}")

            logger.info(f"\nTop performers (by recall@10):")
            top = sorted(with_metrics, key=lambda r: r["metrics"]["recall@10_avg"], reverse=True)[:5]
            for r in top:
                logger.info(
                    f"  {r['article_id']}: {r['metrics']['recall@10_avg']:.1%} "
                    f"(MRR={r['metrics']['mrr_avg']:.1%}, NDCG={r['metrics']['ndcg@10_avg']:.1%})"
                )

            logger.info(f"\nBottom performers (by recall@10):")
            bottom = sorted(with_metrics, key=lambda r: r["metrics"]["recall@10_avg"])[:5]
            for r in bottom:
                logger.info(
                    f"  {r['article_id']}: {r['metrics']['recall@10_avg']:.1%} "
                    f"(MRR={r['metrics']['mrr_avg']:.1%}, NDCG={r['metrics']['ndcg@10_avg']:.1%})"
                )

        # Save report
        report = {
            "summary": {
                "total_documents": len(self.results),
                "documents_with_metrics": len(with_metrics),
            },
            "metrics": {
                "recall@10_avg": float(np.mean([r["metrics"]["recall@10_avg"] for r in with_metrics])) if with_metrics else 0,
                "recall@20_avg": float(np.mean([r["metrics"]["recall@20_avg"] for r in with_metrics])) if with_metrics else 0,
                "mrr_avg": float(np.mean([r["metrics"]["mrr_avg"] for r in with_metrics])) if with_metrics else 0,
                "ndcg@10_avg": float(np.mean([r["metrics"]["ndcg@10_avg"] for r in with_metrics])) if with_metrics else 0,
            },
            "results": self.results,
        }

        self.output_file.write_text(json.dumps(report, indent=2))
        logger.info(f"\n✓ Report saved to {self.output_file}")

    @staticmethod
    def _std(values):
        """Compute standard deviation."""
        if not values or len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test retrieval quality")
    parser.add_argument("--text-dir", default="verified_ground_truth_data/text")
    parser.add_argument("--pdf-dir", default="verified_ground_truth_data/pdf")
    parser.add_argument("--output", default="retrieval_quality_report.json")

    args = parser.parse_args()

    tester = RetrieverQualityTester(
        pdf_dir=args.pdf_dir,
        text_dir=args.text_dir,
        output_file=args.output,
    )
    tester.test_all()
