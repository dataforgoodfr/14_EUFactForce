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

    @abstractmethod
    def download_pdf(self, doi: str, output_dir: str = "pdf") -> bool:
        """Download the first valid PDF found and save it to output_dir. Returns True on success."""
        pass
