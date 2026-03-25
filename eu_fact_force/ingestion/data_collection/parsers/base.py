import logging
import os
from abc import ABC, abstractmethod

import requests


def doi_to_id(doi: str) -> str:
    """Convert a DOI to a filesystem-safe ID."""
    return (
        doi.replace(
            "/",
            "_",
        )
        .replace(".", "_")
        .replace("-", "_")
    )


class MetadataParser(ABC):
    """Base class for all metadata parsers."""

    def __init__(self):
        self.api_name = None
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_metadata(self, doi: str) -> dict:
        """Fetch metadata for a DOI. Returns a dict with at least a "found" key."""
        pass

    @abstractmethod
    def get_pdf_url(self, doi: str) -> list[str]:
        """Return a list of candidate PDF URLs for a DOI, in order of preference."""
        pass

    def _fetch_pdf_content(self, url: str) -> bytes | None:
        """Fetch URL and return content if it is a valid PDF, else None."""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            self.logger.warning(
                f"Content at {url} is not a valid PDF (possibly a paywall page)."
            )
            return None
        return response.content

    def _is_better_than_existing(self, path: str, content: bytes) -> bool:
        """Return True if content should replace the file at path (larger or file absent)."""
        if not os.path.exists(path):
            return True
        return len(content) > os.path.getsize(path)

    def _save_pdf(self, path: str, content: bytes) -> None:
        """Write content to path, or skip if the existing file is already as large or larger."""
        if self._is_better_than_existing(path, content):
            with open(path, "wb") as f:
                f.write(content)
        else:
            self.logger.info(
                f"Skipping {path}: existing file is already as large or larger."
            )

    def download_pdf(self, doi: str, output_dir: str = "pdf") -> bool:
        """Download the first valid PDF found and save it to output_dir. Returns True on success."""
        output_path = os.path.join(output_dir, f"{doi_to_id(doi)}_{self.api_name}.pdf")
        for url in self.get_pdf_url(doi):
            try:
                content = self._fetch_pdf_content(url)
            except Exception as e:
                self.logger.error(f"Download failed for {url}: {e}")
                continue
            if content is None:
                continue
            self._save_pdf(output_path, content)
            return True
        return False
