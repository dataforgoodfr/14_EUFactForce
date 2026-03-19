import os
from abc import ABC, abstractmethod

import requests

from utils import doi_to_id


class MetadataParser(ABC):
    """Base class for all metadata parsers."""

    @abstractmethod
    def get_metadata(self, doi: str) -> dict:
        """Fetch metadata for a DOI. Returns a dict with at least a "found" key."""
        pass

    @abstractmethod
    def get_pdf_url(self, doi: str) -> list[str]:
        """Return a list of candidate PDF URLs for a DOI, in order of preference."""
        pass

    def download_pdf(self, doi: str, output_dir: str = "pdf") -> bool:
        """Download the first valid PDF found and save it to output_dir. Returns True on success."""
        output_path = os.path.join(output_dir, f"{doi_to_id(doi)}.pdf")
        pdf_urls = self.get_pdf_url(doi)
        if not pdf_urls:
            return False
        try:
            for pdf_url in pdf_urls:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()
                if not response.content.startswith(b"%PDF"):
                    print(f"Content at {pdf_url} is not a valid PDF (possibly a paywall page).")
                    continue
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Download failed: {e}")
            return False
