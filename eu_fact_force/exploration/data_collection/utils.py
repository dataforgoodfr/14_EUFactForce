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


def dict_to_string(d: dict) -> str:
    """Convert a dictionary to a string for display."""
    return "\n".join(f"{k}: {v}" for k, v in d.items())
