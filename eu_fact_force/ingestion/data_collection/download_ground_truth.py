"""
Download PDFs and extract ground truth text for articles in verified_ground_truth.csv.

For each arXiv article:
  - Downloads the PDF to {output_dir}/pdf/{article_id}.pdf
  - Downloads the LaTeX source tar, extracts all .tex files, and writes
    cleaned text to {output_dir}/text/{article_id}.txt

The extracted text is used as the reference ("ground truth") when measuring
how well the PDF parser reproduces the original content.

Usage:
    python -m eu_fact_force.ingestion.data_collection.download_ground_truth \\
        --csv verified_ground_truth.csv \\
        --output-dir ./verified_ground_truth_data \\
        --workers 4
"""

import argparse
import csv
import json
import logging
import re
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 60  # seconds — source tarballs can be large


def download_article(article: dict, pdf_dir: Path, text_dir: Path) -> dict:
    """
    Download PDF and extract LaTeX text for one article row from the CSV.

    Returns a result dict with keys: article_id, status, pdf_path, text_path, error.
    """
    article_id = article["article_id"]
    source = article["source"]

    if source != "arxiv":
        logger.warning("download.unsupported_source id=%s source=%s", article_id, source)
        return {"article_id": article_id, "status": "skipped", "reason": f"unsupported source: {source}"}

    safe_id = article_id.replace(":", "_").replace("/", "_")
    pdf_path = pdf_dir / f"{safe_id}.pdf"
    text_path = text_dir / f"{safe_id}.txt"

    # Skip if both already present
    if pdf_path.exists() and text_path.exists():
        logger.info("download.skip id=%s reason=already_exists", article_id)
        return {"article_id": article_id, "status": "skipped", "reason": "already_exists",
                "pdf_path": str(pdf_path), "text_path": str(text_path)}

    pdf_ok = _download_pdf(article["pdf_url"], pdf_path)
    text_ok = _download_arxiv_latex(article["text_url"], text_path)

    status = "success" if pdf_ok and text_ok else ("partial" if pdf_ok or text_ok else "failed")
    result = {
        "article_id": article_id,
        "status": status,
        "pdf_path": str(pdf_path) if pdf_ok else None,
        "text_path": str(text_path) if text_ok else None,
    }
    logger.info("download.done id=%s status=%s", article_id, status)
    return result


def download_all(
    csv_path: str,
    output_dir: str,
    workers: int = 4,
) -> list[dict]:
    """
    Download all articles from the ground truth CSV in parallel.

    Writes a download_manifest.json into output_dir summarising results.
    """
    pdf_dir = Path(output_dir) / "pdf"
    text_dir = Path(output_dir) / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    with open(csv_path, encoding="utf-8") as f:
        articles = list(csv.DictReader(f))

    logger.info("download.start total=%d workers=%d", len(articles), workers)

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_article, a, pdf_dir, text_dir): a["article_id"]
            for a in articles
        }
        for future in as_completed(futures):
            results.append(future.result())

    successful = [r for r in results if r["status"] in ("success", "partial")]
    failed = [r for r in results if r["status"] == "failed"]

    manifest = {
        "csv": csv_path,
        "total": len(articles),
        "successful": len(successful),
        "failed": len(failed),
        "results": results,
    }
    manifest_path = Path(output_dir) / "download_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nDownload complete: {len(successful)}/{len(articles)} succeeded")
    if failed:
        print(f"Failed ({len(failed)}):")
        for r in failed:
            print(f"  {r['article_id']}: {r.get('error', 'unknown')}")
    print(f"Manifest: {manifest_path}")

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF file. Returns True on success."""
    if dest.exists():
        return True
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        if not resp.content.startswith(b"%PDF"):
            logger.warning("download.not_a_pdf url=%s", url)
            return False
        dest.write_bytes(resp.content)
        logger.info("download.pdf_ok url=%s size=%d", url, len(resp.content))
        return True
    except Exception as e:
        logger.warning("download.pdf_failed url=%s error=%s", url, e)
        return False


def _download_arxiv_latex(source_url: str, dest: Path) -> bool:
    """
    Download an arXiv source tarball, extract all .tex files, clean and
    concatenate them, then write plain text to dest. Returns True on success.
    """
    if dest.exists():
        return True
    try:
        resp = requests.get(source_url, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("download.latex_fetch_failed url=%s error=%s", source_url, e)
        return False

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = Path(tmpdir) / "source.tar.gz"
            tar_path.write_bytes(resp.content)

            try:
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(tmpdir)
            except tarfile.TarError:
                # Some arXiv sources are bare .tex, not tar'd
                text = _clean_latex(resp.content)
                dest.write_text(text, encoding="utf-8")
                return bool(text.strip())

            tex_files = sorted(Path(tmpdir).rglob("*.tex"))
            if not tex_files:
                logger.warning("download.no_tex_found url=%s", source_url)
                return False

            # Concatenate all .tex files (main file first if identifiable)
            parts = []
            for tex in tex_files:
                try:
                    parts.append(_clean_latex(tex.read_bytes()))
                except Exception:
                    pass

            text = "\n\n".join(p for p in parts if p.strip())
            dest.write_text(text, encoding="utf-8")
            logger.info("download.latex_ok url=%s chars=%d", source_url, len(text))
            return bool(text.strip())

    except Exception as e:
        logger.warning("download.latex_extract_failed url=%s error=%s", source_url, e)
        return False


def _clean_latex(raw: bytes) -> str:
    """Strip LaTeX markup and return readable plain text."""
    text = raw.decode("utf-8", errors="ignore")
    # Remove comments
    text = re.sub(r"%[^\n]*", "", text)
    # Unwrap common commands that enclose text: \cmd{content} → content
    text = re.sub(r"\\(?:textbf|textit|emph|textrm|texttt|text|mbox)\{([^}]*)\}", r"\1", text)
    # Remove remaining LaTeX commands (with or without braces)
    text = re.sub(r"\\[a-zA-Z]+\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    # Remove leftover braces and math delimiters
    text = re.sub(r"[{}$]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to verified_ground_truth.csv")
    parser.add_argument("--output-dir", default="./verified_ground_truth_data")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    results = download_all(args.csv, args.output_dir, args.workers)
    failed = sum(1 for r in results if r["status"] == "failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
