from eu_fact_force.ingestion.services import hash_doi


def test_hash_doi():
    """Test the hash_doi function."""
    assert (
        hash_doi("10.1234/example")
        == "68b8f7c42b3c20b5b49680c9913c11520ec81f3022f0509564140d4ed3f70d78"
    )
