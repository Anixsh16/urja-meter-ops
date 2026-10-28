import asyncio
import time
from collections import OrderedDict
from datetime import UTC, datetime

from urja.models import Meta


class TTLCache:
    """Bounded process-local cache; striped locks collapse identical concurrent reads."""

    def __init__(self, capacity=128, clock=time.monotonic, now=lambda: datetime.now(UTC)):
        self.capacity = capacity
        self.clock = clock
        self.now = now
        self.entries = OrderedDict()
        self.locks = [asyncio.Lock() for _ in range(16)]

    async def get(self, key, ttl, loader):
        async with self.locks[hash(key) % len(self.locks)]:
            entry = self.entries.get(key)
            if entry is not None and self.clock() - entry[0] < ttl:
                self.entries.move_to_end(key)
                return entry[2], Meta(
                    fetched_at=entry[1],
                    cache="hit",
                    age_seconds=max(0, int(self.clock() - entry[0])),
                )
            # Expired entries are never used as a silent fallback if refresh fails.
            self.entries.pop(key, None)
            value = await loader()
            fetched = self.now()
            self.entries[key] = (self.clock(), fetched, value)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            return value, Meta(fetched_at=fetched, cache="miss")
