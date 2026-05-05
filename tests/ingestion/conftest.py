import pytest


@pytest.fixture(scope="module")
def vcr_config():
    # Strip the Unpaywall email from recorded cassettes so it is not committed to git.
    return {"filter_query_parameters": ["email"]}
