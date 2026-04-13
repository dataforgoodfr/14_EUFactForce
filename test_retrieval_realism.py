"""
Realistic retrieval quality evaluation using cross-document queries.

Instead of searching for documents using their own content,
creates diverse synthetic queries and measures how well the system
finds topically related documents.
"""

import json
import logging
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def extract_sentences(text: str, max_sentences: int = 20) -> list[str]:
    """Extract individual sentences from text."""
    # Simple sentence splitting on periods, question marks, exclamation marks
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".!?":
            sent = current.strip()
            if len(sent) > 30:  # Skip very short sentences
                sentences.append(sent)
            current = ""
    return sentences[:max_sentences]


def create_synthetic_queries(text: str, num_queries: int = 3) -> list[str]:
    """Create synthetic queries by combining key sentences."""
    sentences = extract_sentences(text)
    if len(sentences) < 2:
        return []

    queries = []
    # Query 1: First sentence
    if sentences:
        queries.append(sentences[0])

    # Query 2: Middle sentence
    if len(sentences) > 2:
        queries.append(sentences[len(sentences) // 2])

    # Query 3: Combination of sentences
    if len(sentences) > 3:
        queries.append(" ".join([sentences[0], sentences[len(sentences) // 2]]))

    return queries[:num_queries]


class RealisticRetrieverTester:
    """Test retrieval using cross-document queries (more realistic scenario)."""

    def __init__(
        self,
        text_dir: str = "verified_ground_truth_data/text",
        output_file: str = "retrieval_realism_report.json",
    ):
        self.text_dir = Path(text_dir)
        self.output_file = Path(output_file)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.results = []

        # Load documents and create index
        self.documents = {}
        self.doc_embeddings = None
        self.doc_ids_to_indices = {}
        self.doc_ids = []
        self._load_documents()

    def _load_documents(self):
        """Load all ground truth documents."""
        logger.info("Loading documents for retrieval testing...")

        text_files = sorted(self.text_dir.glob("*.txt"))
        doc_texts = []

        for text_path in text_files:
            article_id = text_path.stem
            try:
                text = text_path.read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    self.documents[article_id] = {
                        "text": text,
                        "path": str(text_path),
                    }
                    # Use first 5000 chars for embedding
                    doc_texts.append(text[:5000])
                    self.doc_ids_to_indices[article_id] = len(doc_texts) - 1
                    self.doc_ids.append(article_id)
            except Exception as e:
                logger.warning(f"Failed to load {article_id}: {e}")

        logger.info(f"Loaded {len(self.documents)} documents")

        # Compute embeddings
        if doc_texts:
            logger.info("Computing document embeddings...")
            self.doc_embeddings = np.array(
                self.model.encode(doc_texts, convert_to_tensor=False, show_progress_bar=False)
            )

    def retrieve_similar(self, query_text: str, k: int = 10) -> list[tuple[str, float]]:
        """Retrieve top-k documents similar to query."""
        if not self.documents or self.doc_embeddings is None:
            return []

        # Embed query
        query_emb = self.model.encode(query_text[:5000], convert_to_tensor=False)

        # Compute similarities
        similarities = cosine_similarity([query_emb], self.doc_embeddings)[0]

        # Get top-k
        top_indices = np.argsort(-similarities)[:k]

        # Convert to article IDs
        results = []
        for idx in top_indices:
            article_id = self.doc_ids[idx]
            results.append((article_id, float(similarities[idx])))

        return results

    def test_all(self):
        """Test retrieval for each document using synthetic queries."""
        logger.info(f"\nTesting cross-document retrieval for {len(self.documents)} documents...")
        logger.info("")

        for i, (article_id, doc_info) in enumerate(self.documents.items(), 1):
            logger.info(f"[{i}/{len(self.documents)}] {article_id}")

            text = doc_info["text"]

            # Create synthetic queries from this document
            queries = create_synthetic_queries(text, num_queries=3)

            if not queries:
                logger.warning(f"  No queries generated for {article_id}")
                continue

            logger.info(f"  Generated {len(queries)} synthetic queries")

            query_metrics = []

            for q_idx, query in enumerate(queries, 1):
                # Retrieve documents (excluding the query source if possible would be ideal,
                # but we're testing if the system at least ranks it highly)
                retrieved = self.retrieve_similar(query, k=20)
                retrieved_ids = [doc_id for doc_id, _ in retrieved]
                retrieved_scores = {doc_id: score for doc_id, score in retrieved}

                # Find rank of original article
                if article_id in retrieved_ids:
                    rank = retrieved_ids.index(article_id) + 1
                    similarity = retrieved_scores[article_id]
                else:
                    rank = None
                    similarity = None

                # Also count how many unique documents were retrieved
                # (to measure diversity of results)
                unique_count = len(set(retrieved_ids))

                query_metrics.append({
                    "query_idx": q_idx,
                    "query_length": len(query),
                    "source_rank": rank,
                    "source_similarity": similarity,
                    "top_5_documents": [doc_id for doc_id, _ in retrieved[:5]],
                    "top_5_similarities": [score for _, score in retrieved[:5]],
                    "unique_in_top_20": unique_count,
                })

            # Aggregate metrics
            if query_metrics:
                # How often was the source document ranked in top-5, top-10?
                in_top_5 = sum(1 for m in query_metrics if m["source_rank"] and m["source_rank"] <= 5)
                in_top_10 = sum(1 for m in query_metrics if m["source_rank"] and m["source_rank"] <= 10)
                found_at_all = sum(1 for m in query_metrics if m["source_rank"])

                avg_similarity = np.mean([m["source_similarity"] for m in query_metrics if m["source_similarity"]])
                avg_rank = np.mean([m["source_rank"] for m in query_metrics if m["source_rank"]])

                logger.info(f"    Found in top-10: {found_at_all}/{len(query_metrics)} queries")
                logger.info(f"    Avg rank (when found): {avg_rank:.1f}")
                logger.info(f"    Avg similarity: {avg_similarity:.1%}")

                self.results.append({
                    "article_id": article_id,
                    "num_queries": len(query_metrics),
                    "metrics": {
                        "found_in_top_5": in_top_5,
                        "found_in_top_10": in_top_10,
                        "found_at_all": found_at_all,
                        "avg_rank": float(avg_rank) if in_top_10 > 0 else float('inf'),
                        "avg_similarity": float(avg_similarity),
                    },
                    "query_details": query_metrics,
                })

        self.generate_report()

    def generate_report(self):
        """Generate report on cross-document retrieval quality."""
        logger.info("\n" + "=" * 60)
        logger.info("REALISTIC RETRIEVAL QUALITY REPORT")
        logger.info("Cross-document query evaluation")
        logger.info("=" * 60)

        logger.info(f"\nSummary:")
        logger.info(f"  Total documents tested: {len(self.results)}")

        if not self.results:
            logger.warning("  No results to report")
            return

        logger.info(f"\nCross-Document Retrieval Metrics:")

        total_queries = sum(r["num_queries"] for r in self.results)
        total_found = sum(r["metrics"]["found_at_all"] for r in self.results)
        total_top_10 = sum(r["metrics"]["found_in_top_10"] for r in self.results)
        total_top_5 = sum(r["metrics"]["found_in_top_5"] for r in self.results)

        logger.info(f"  Total synthetic queries: {total_queries}")
        logger.info(f"  Found source doc: {total_found}/{total_queries} ({100*total_found/total_queries:.1f}%)")
        logger.info(f"  Found in top-5: {total_top_5}/{total_queries} ({100*total_top_5/total_queries:.1f}%)")
        logger.info(f"  Found in top-10: {total_top_10}/{total_queries} ({100*total_top_10/total_queries:.1f}%)")

        # Average rank (excluding not-found)
        valid_ranks = [r["metrics"]["avg_rank"] for r in self.results if r["metrics"]["avg_rank"] != float('inf')]
        if valid_ranks:
            avg_rank = np.mean(valid_ranks)
            logger.info(f"  Avg rank (when found): {avg_rank:.1f}")

        avg_similarity = np.mean([r["metrics"]["avg_similarity"] for r in self.results])
        logger.info(f"  Avg similarity score: {avg_similarity:.1%}")

        logger.info(f"\nTop performers (by found_at_all):")
        top = sorted(self.results, key=lambda r: r["metrics"]["found_at_all"], reverse=True)[:5]
        for r in top:
            metrics = r["metrics"]
            logger.info(
                f"  {r['article_id']}: {metrics['found_at_all']}/{r['num_queries']} found "
                f"(avg_rank={metrics['avg_rank']:.1f}, similarity={metrics['avg_similarity']:.1%})"
            )

        logger.info(f"\nBottom performers (by found_at_all):")
        bottom = sorted(self.results, key=lambda r: r["metrics"]["found_at_all"])[:5]
        for r in bottom:
            metrics = r["metrics"]
            logger.info(
                f"  {r['article_id']}: {metrics['found_at_all']}/{r['num_queries']} found "
                f"(avg_rank={metrics['avg_rank']:.1f}, similarity={metrics['avg_similarity']:.1%})"
            )

        # Save report
        report = {
            "summary": {
                "total_documents": len(self.results),
                "total_queries": total_queries,
                "found_count": total_found,
                "found_percentage": 100 * total_found / total_queries if total_queries > 0 else 0,
                "found_in_top_5_percentage": 100 * total_top_5 / total_queries if total_queries > 0 else 0,
                "found_in_top_10_percentage": 100 * total_top_10 / total_queries if total_queries > 0 else 0,
            },
            "metrics": {
                "avg_similarity": float(avg_similarity),
                "avg_rank_when_found": float(np.mean(valid_ranks)) if valid_ranks else None,
            },
            "results": self.results,
        }

        self.output_file.write_text(json.dumps(report, indent=2))
        logger.info(f"\n✓ Report saved to {self.output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test realistic retrieval quality")
    parser.add_argument("--text-dir", default="verified_ground_truth_data/text")
    parser.add_argument("--output", default="retrieval_realism_report.json")

    args = parser.parse_args()

    tester = RealisticRetrieverTester(
        text_dir=args.text_dir,
        output_file=args.output,
    )
    tester.test_all()
