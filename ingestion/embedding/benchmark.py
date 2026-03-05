"""
Embedding Model Benchmark for EU Fact Force.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Support direct script execution: python ingestion/embedding/benchmark.py
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from ingestion.embedding.benchmark_runner import run_cli


def main() -> None:
    """CLI entrypoint."""
    run_cli()


if __name__ == "__main__":
    main()
