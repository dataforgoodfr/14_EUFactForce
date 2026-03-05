"""Shared timing helpers used across ingestion modules."""

from __future__ import annotations

from time import perf_counter
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def timed_call(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> tuple[T, float]:
    """Run a callable and return its result plus elapsed seconds."""
    start = perf_counter()
    result = func(*args, **kwargs)
    return result, perf_counter() - start
