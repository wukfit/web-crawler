"""Tests for token bucket rate limiter."""

import asyncio

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

        await asyncio.sleep(0.25)
        await asyncio.wait_for(bucket.acquire(), timeout=0.2)

    async def test_burst_then_blocks(self):
        bucket = TokenBucket(rate=5.0)
        for _ in range(5):
            await asyncio.wait_for(bucket.acquire(), timeout=0.1)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bucket.acquire(), timeout=0.05)

    async def test_set_rate_changes_refill_speed(self):
        bucket = TokenBucket(rate=100.0)
        for _ in range(100):
            await bucket.acquire()

        await bucket.set_rate(2.0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bucket.acquire(), timeout=0.1)

    def test_rejects_zero_rate(self):
        with pytest.raises(ValueError, match="rate"):
            TokenBucket(rate=0.0)

    def test_rejects_negative_rate(self):
        with pytest.raises(ValueError, match="rate"):
            TokenBucket(rate=-1.0)

    async def test_set_rate_rejects_zero(self):
        bucket = TokenBucket(rate=10.0)
        with pytest.raises(ValueError, match="rate"):
            await bucket.set_rate(0.0)
