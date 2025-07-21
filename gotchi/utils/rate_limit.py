"""
gotchi.utils.rate_limit
=======================

Generic token-bucket rate-limiter.

Usage
-----

>>> from gotchi.utils.rate_limit import TokenBucket
>>> bucket = TokenBucket(rate=50, capacity=100)    # 50 tokens / second
>>> if bucket.consume(1):
...     do_something()
"""

from __future__ import annotations

import time
from typing import Final


class TokenBucket:
    """
    Classic token-bucket algorithm.

    Parameters
    ----------
    rate
        Token refill rate (tokens **per second**).
    capacity
        Maximum bucket size; defaults to *rate* if omitted.
    """

    def __init__(self, *, rate: float, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate: Final = float(rate)
        self.capacity: Final = float(capacity if capacity is not None else rate)

        self._tokens: float = self.capacity          # start full
        self._timestamp: float = time.perf_counter()  # last refill time

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Attempt to take *tokens* from the bucket.

        Returns
        -------
        bool
            • **True**  – tokens available, bucket debited  
            • **False** – not enough tokens right now
        """
        if tokens <= 0:
            raise ValueError("tokens must be > 0")

        self._refill()

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _refill(self) -> None:
        """Add tokens according to elapsed time."""
        now = time.perf_counter()
        elapsed = now - self._timestamp
        self._timestamp = now

        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    # ------------------------------------------------------------------ #
    # Debug helpers
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # noqa: D401
        return (
            f"<TokenBucket {self._tokens:.2f}/{self.capacity} "
            f"rate={self.rate}/s>"
        )
