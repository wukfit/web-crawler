"""Token bucket rate limiter for async crawling."""

import asyncio
import time


class TokenBucket:
    """Rate limiter using the token bucket algorithm."""

    def __init__(self, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate
        self._max_tokens = rate
        self._tokens = rate
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def set_rate(self, rate: float) -> None:
        """Update the token refill rate and burst size."""
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate
        self._max_tokens = rate

    async def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._max_tokens, self._tokens + elapsed * self._rate
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            await asyncio.sleep(1.0 / self._rate)
