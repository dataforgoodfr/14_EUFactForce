"""
Download PDFs and text versions from ground truth CSV.

Downloads both formats for parser ground truth validation:
  - PDF: from pdf_url
  - Text: from text_url (XML for PMC, source tar for arXiv)

Usage:
    python download_ground_truth.py \
        --csv ground_truth_50_articles.csv \
        --output-dir ./ground_truth_data \
        --workers 4
"""

import csv
import json
import logging
import os
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TextExtractor:
    """Extract text from different formats."""

    @staticmethod
    def extract_pmc_xml(xml_content: bytes) -> str:
        """Extract readable text from PMC XML."""
        try:
            root = ET.fromstring(xml_content)

            # Namespaces used in PMC XML
            ns = {"": "http://www.ncbi.nlm.nih.gov/JATS"}

            # Extract title
            title_elem = root.find(".//front/article-meta/title-group/article-title", ns)
            title = title_elem.text if title_elem is not None else ""

            # Extract abstract
            abstract_elem = root.find(".//front/article-meta/abstract", ns)
            abstract = ""
            if abstract_elem is not None:
                abstract_parts = []
                for p in abstract_elem.findall(".//p", ns):
                    if p.text:
                        abstract_parts.append(p.text)
                abstract = " ".join(abstract_parts)

            # Extract body text
            body_parts = []
            body_elem = root.find(".//body", ns)
            if body_elem is not None:
                for p in body_elem.findall(".//p", ns):
                    text = "".join(p.itertext()).strip()
                    if text:
                        body_parts.append(text)

            # Combine
            text = f"# {title}\n\n"
            if abstract:
                text += f"## Abstract\n\n{abstract}\n\n"
            text += "## Body\n\n" + "\n\n".join(body_parts)

            return text

        except Exception as e:
            logger.warning(f"Failed to extract PMC XML: {e}")
            return ""

    @staticmethod
    def extract_arxiv_tex(tex_content: bytes) -> str:
        """Extract text from arXiv .tex source."""
        try:
            text = tex_content.decode("utf-8", errors="ignore")
            # Remove LaTeX commands (simplified)
            import re

            # Remove comments
            text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
            # Remove LaTeX commands
            text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
            text = re.sub(r"\\[a-zA-Z]+", "", text)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text)

            return text

        except Exception as e:
            logger.warning(f"Failed to extract arXiv TeX: {e}")
            return ""


class GroundTruthDownloader:
    """Download articles and extract text versions."""

    def __init__(self, output_dir: str, timeout: int = 30):
        self.output_dir = output_dir
        self.timeout = timeout
        self.extractor = TextExtractor()

        # Create output directories
        self.pdf_dir = os.path.join(output_dir, "pdf")
        self.text_dir = os.path.join(output_dir, "text")
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.text_dir, exist_ok=True)

    def download_pmc(self, article_id: str, pdf_url: str, xml_url: str) -> dict:
        """Download PMC article (PDF + XML)."""
        try:
            # Extract PMC ID
            pmc_id = article_id.replace("PMC", "")
            logger.info(f"Downloading {article_id}...")

            # Download PDF
            pdf_path = os.path.join(self.pdf_dir, f"{article_id}.pdf")
            try:
                response = requests.get(pdf_url, timeout=self.timeout)
                response.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"  ✓ PDF: {os.path.getsize(pdf_path):,} bytes")
            except Exception as e:
                logger.warning(f"  ✗ PDF download failed: {e}")
                pdf_path = None

            # Download XML and extract text
            text_path = os.path.join(self.text_dir, f"{article_id}.txt")
            try:
                response = requests.get(xml_url, timeout=self.timeout)
                response.raise_for_status()
                text = self.extractor.extract_pmc_xml(response.content)
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"  ✓ Text: {len(text):,} chars")
            except Exception as e:
                logger.warning(f"  ✗ Text download failed: {e}")
                text_path = None

            return {
                "article_id": article_id,
                "status": "success" if pdf_path and text_path else "partial",
                "pdf_path": pdf_path,
                "text_path": text_path,
            }

        except Exception as e:
            logger.error(f"Failed to download {article_id}: {e}")
            return {
                "article_id": article_id,
                "status": "failed",
                "error": str(e),
            }

    def download_arxiv(self, article_id: str, pdf_url: str, source_url: str) -> dict:
        """Download arXiv preprint (PDF + source)."""
        try:
            logger.info(f"Downloading {article_id}...")

            # Download PDF
            pdf_path = os.path.join(self.pdf_dir, f"{article_id}.pdf")
            try:
                response = requests.get(pdf_url, timeout=self.timeout)
                response.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"  ✓ PDF: {os.path.getsize(pdf_path):,} bytes")
            except Exception as e:
                logger.warning(f"  ✗ PDF download failed: {e}")
                pdf_path = None

            # Download source (tar.gz) and extract
            text_path = os.path.join(self.text_dir, f"{article_id}.txt")
            try:
                response = requests.get(source_url, timeout=self.timeout)
                response.raise_for_status()

                # Extract from tar.gz
                with tempfile.TemporaryDirectory() as tmpdir:
                    tar_path = os.path.join(tmpdir, "source.tar.gz")
                    with open(tar_path, "wb") as f:
                        f.write(response.content)

                    # Extract and find .tex files
                    with tarfile.open(tar_path, "r:gz") as tar:
                        tar.extractall(tmpdir)

                    # Find and read .tex file
                    tex_files = list(Path(tmpdir).rglob("*.tex"))
                    if tex_files:
                        with open(tex_files[0], "rb") as f:
                            text = self.extractor.extract_arxiv_tex(f.read())
                        with open(text_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        logger.info(f"  ✓ Text: {len(text):,} chars")
                    else:
                        logger.warning(f"  ✗ No .tex file found in source")
                        text_path = None

            except Exception as e:
                logger.warning(f"  ✗ Source download failed: {e}")
                text_path = None

            return {
                "article_id": article_id,
                "status": "success" if pdf_path and text_path else "partial",
                "pdf_path": pdf_path,
                "text_path": text_path,
            }

        except Exception as e:
            logger.error(f"Failed to download {article_id}: {e}")
            return {
                "article_id": article_id,
                "status": "failed",
                "error": str(e),
            }

    def download_all(self, csv_path: str, workers: int = 4) -> list[dict]:
        """Download all articles from CSV."""
        # Load CSV
        articles = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            articles = list(reader)

        logger.info(f"Downloading {len(articles)} articles...")
        logger.info(f"Output: {self.output_dir}/")

        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}

            for article in articles:
                article_id = article["article_id"]
                source = article["source"]

                if source == "pubmed_central":
                    future = executor.submit(
                        self.download_pmc,
                        article_id,
                        article["pdf_url"],
                        article["text_url"],
                    )
                elif source == "arxiv":
                    future = executor.submit(
                        self.download_arxiv,
                        article_id,
                        article["pdf_url"],
                        article["text_url"],
                    )
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue

                futures[future] = article_id

            # Collect results
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # Summary
        successful = [r for r in results if r["status"] in ["success", "partial"]]
        failed = [r for r in results if r["status"] == "failed"]

        logger.info(f"\n{'='*60}")
        logger.info(f"DOWNLOAD COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Successful: {len(successful)}/{len(articles)}")
        logger.info(f"Failed: {len(failed)}/{len(articles)}")
        logger.info(f"\nOutput directories:")
        logger.info(f"  PDFs: {self.pdf_dir}/ ({len(os.listdir(self.pdf_dir))} files)")
        logger.info(f"  Texts: {self.text_dir}/ ({len(os.listdir(self.text_dir))} files)")

        # Save manifest
        manifest = {
            "csv_file": csv_path,
            "total_articles": len(articles),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }
        manifest_path = os.path.join(self.output_dir, "download_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Manifest: {manifest_path}")

        return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download ground truth articles.")
    parser.add_argument("--csv", required=True, help="Input CSV file")
    parser.add_argument(
        "--output-dir", default="./ground_truth_data", help="Output directory"
    )
    parser.add_argument("--workers", type=int, default=4, help="Download workers")

    args = parser.parse_args()

    downloader = GroundTruthDownloader(args.output_dir)
    downloader.download_all(args.csv, args.workers)
