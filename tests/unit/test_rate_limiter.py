"""Tests for token bucket rate limiter."""

import asyncio
import time

import pytest

from web_crawler.crawler.rate_limiter import TokenBucket


class TestTokenBucket:
    async def test_acquire_succeeds_when_tokens_available(self):
        bucket = TokenBucket(rate=10.0)
        await asyncio.wait_for(bucket.acquire(), timeout=0.1)

    async def test_acquire_blocks_when_exhausted(self):
        bucket = TokenBucket(rate=2.0)
        await bucket.acquire()
        await bucket.acquire()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bucket.acquire(), timeout=0.1)

    async def test_tokens_refill_over_time(self):
        bucket = TokenBucket(rate=10.0)
        for _ in range(10):
            await bucket.acquire()

        await asyncio.sleep(0.15)
        await asyncio.wait_for(bucket.acquire(), timeout=0.1)

    async def test_rate_limits_throughput(self):
        bucket = TokenBucket(rate=20.0)
        start = time.monotonic()

        for _ in range(30):
            await bucket.acquire()

        elapsed = time.monotonic() - start
        # First 20 instant, next 10 at 20/s = 0.5s minimum
        assert elapsed >= 0.4

    async def test_set_rate_changes_refill_speed(self):
        bucket = TokenBucket(rate=100.0)
        for _ in range(100):
            await bucket.acquire()

        bucket.set_rate(2.0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bucket.acquire(), timeout=0.1)
