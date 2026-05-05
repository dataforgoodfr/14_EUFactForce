import os

import pytest


@pytest.fixture(scope="module")
def vcr_config():
    # Strip the Unpaywall email from recorded cassettes so it is not committed to git.
    return {"filter_query_parameters": ["email"]}


@pytest.fixture(autouse=True)
def unpaywall_email(monkeypatch):
    # UnpaywallMetadataParser checks UNPAYWALL_EMAIL before making any HTTP request,
    # so it short-circuits to {"found": False} if the var is missing — VCR never fires.
    # A placeholder is enough during replay; the real value is needed only when recording.
    if not os.environ.get("UNPAYWALL_EMAIL"):
        monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")
