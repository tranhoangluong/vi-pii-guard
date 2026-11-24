"""Session storage for reversible placeholders (``[PHONE_1]`` -> original value)."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from vi_pii_guard.domain import EntityType


@dataclass
class RedactionSession:
    """Placeholder mapping for one conversation.

    The same value always gets the same placeholder inside a session, so the
    LLM can still reason that two mentions refer to the same person.
    """

    session_id: str
    forward: dict[tuple[EntityType, str], str] = field(default_factory=dict)
    reverse: dict[str, str] = field(default_factory=dict)
    counters: dict[EntityType, int] = field(default_factory=dict)

    def placeholder_for(self, entity_type: EntityType, key: str, original: str) -> str:
        existing = self.forward.get((entity_type, key))
        if existing is not None:
            return existing
        number = self.counters.get(entity_type, 0) + 1
        self.counters[entity_type] = number
        placeholder = f"[{entity_type.value}_{number}]"
        self.forward[(entity_type, key)] = placeholder
        self.reverse[placeholder] = original
        return placeholder


class Vault(Protocol):
    """Port for session storage. Production deployments may add a Redis adapter."""

    def load(self, session_id: str) -> RedactionSession | None: ...

    def save(self, session: RedactionSession) -> None: ...

    def delete(self, session_id: str) -> None: ...


class InMemoryVault:
    """Thread-safe in-process vault with sliding TTL and LRU eviction.

    Mappings contain raw PII, so they are never persisted or logged.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 3600.0,
        max_sessions: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._clock = clock
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, RedactionSession]] = OrderedDict()

    def load(self, session_id: str) -> RedactionSession | None:
        with self._lock:
            self._purge_expired()
            item = self._store.get(session_id)
            if item is None:
                return None
            self._store[session_id] = (self._clock() + self._ttl, item[1])
            self._store.move_to_end(session_id)
            return item[1]

    def save(self, session: RedactionSession) -> None:
        with self._lock:
            self._store[session.session_id] = (self._clock() + self._ttl, session)
            self._store.move_to_end(session.session_id)
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._store)

    def _purge_expired(self) -> None:
        # Every write moves the key to the end with expiry now + ttl, so the
        # dict is ordered by expiry and we only need to pop from the front.
        now = self._clock()
        while self._store:
            oldest_key = next(iter(self._store))
            if self._store[oldest_key][0] > now:
                break
            del self._store[oldest_key]
