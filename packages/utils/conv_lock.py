from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator


class ConversationLockManager:
    """Reference-counted per-conversation async lock manager.

    Locks are automatically removed when no coroutines are waiting for
    or holding them, preventing unbounded memory growth over long runtimes.

    Usage::

        manager = ConversationLockManager()
        async with manager.acquire("conv_key"):
            ...
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._counts: dict[str, int] = defaultdict(int)
        self._meta: asyncio.Lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: str) -> AsyncGenerator[None, None]:
        async with self._meta:
            lock = self._locks.setdefault(key, asyncio.Lock())
            self._counts[key] += 1
        try:
            async with lock:
                yield
        finally:
            async with self._meta:
                self._counts[key] -= 1
                if self._counts[key] == 0:
                    self._locks.pop(key, None)
                    self._counts.pop(key, None)

    def active_count(self) -> int:
        """Return number of currently tracked locks (for diagnostics)."""
        return len(self._locks)
