"""Small in-process caches for hot SendSprint paths."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

_MISSING = object()


@dataclass(frozen=True)
class CacheStats:
    """Snapshot of cache counters."""

    maxsize: int
    ttl_s: float | None
    size: int
    hits: int
    misses: int
    evictions: int


class LruTtlCache(Generic[K, V]):
    """Tiny thread-safe LRU cache with optional TTL.

    It is intentionally dependency-free so it can be reused by template rendering,
    sprint-plan memoization, and provider clients without pulling in a cache server.
    """

    def __init__(self, *, maxsize: int = 128, ttl_s: float | None = None) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.maxsize = maxsize
        self.ttl_s = ttl_s
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: K, default: object = _MISSING) -> V | object:
        """Return a cached value, or ``default`` when missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return default
            created_at, value = entry
            if self._expired(created_at):
                self._data.pop(key, None)
                self._misses += 1
                return default
            self._data.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: K, value: V) -> V:
        """Store and return ``value``."""
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)
                self._evictions += 1
        return value

    def get_or_set(self, key: K, factory: Callable[[], V]) -> V:
        """Return cached value, computing it once when absent."""
        cached = self.get(key, _MISSING)
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]
        value = factory()
        return self.set(key, value)

    def clear(self) -> None:
        """Drop entries and reset counters."""
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def stats(self) -> CacheStats:
        """Return current counters."""
        with self._lock:
            self._purge_expired()
            return CacheStats(
                maxsize=self.maxsize,
                ttl_s=self.ttl_s,
                size=len(self._data),
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )

    def _expired(self, created_at: float) -> bool:
        return self.ttl_s is not None and (time.monotonic() - created_at) > self.ttl_s

    def _purge_expired(self) -> None:
        if self.ttl_s is None:
            return
        expired = [key for key, (created_at, _) in self._data.items() if self._expired(created_at)]
        for key in expired:
            self._data.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._data)
