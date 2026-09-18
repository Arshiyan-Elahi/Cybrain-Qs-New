"""Small circuit breaker for remote AI health probes."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class ProbeResult:
    online: bool
    checked_at: float
    reason: str | None = None


class CircuitBreaker:
    """
    Fail-open after cooldown so a dead remote PC does not stall every request.

    Independent instances are used for LLM and embedding probes.
    """

    def __init__(
        self,
        *,
        cooldown_seconds: float,
        on_open: Callable[[str], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_retry: Callable[[], None] | None = None,
        name: str = "remote",
    ) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._lock = threading.Lock()
        self._open_until = 0.0
        self._last: ProbeResult | None = None
        self._was_open = False
        self._on_open = on_open
        self._on_close = on_close
        self._on_retry = on_retry
        self.name = name
        self._retry_notified = False

    @property
    def last(self) -> ProbeResult | None:
        with self._lock:
            return self._last

    def is_cooling_down(self) -> bool:
        with self._lock:
            return time.monotonic() < self._open_until

    def seconds_until_retry(self) -> float:
        with self._lock:
            return max(0.0, self._open_until - time.monotonic())

    def should_probe(self) -> bool:
        cooling = self.is_cooling_down()
        if cooling:
            self._retry_notified = False
            return False
        if self._was_open and not self._retry_notified and self._on_retry:
            self._retry_notified = True
            self._on_retry()
        return True

    def record_success(self) -> ProbeResult:
        result = ProbeResult(online=True, checked_at=time.time(), reason=None)
        with self._lock:
            was_open = self._was_open
            self._open_until = 0.0
            self._last = result
            self._was_open = False
            self._retry_notified = False
        if was_open and self._on_close:
            self._on_close()
        return result

    def record_failure(self, reason: str) -> ProbeResult:
        result = ProbeResult(online=False, checked_at=time.time(), reason=reason)
        opened_now = False
        with self._lock:
            if not self._was_open:
                opened_now = True
            self._open_until = time.monotonic() + self.cooldown_seconds
            self._last = result
            self._was_open = True
            self._retry_notified = False
        if opened_now and self._on_open:
            self._on_open(reason)
        return result

    def cached_offline(self) -> bool:
        last = self.last
        return bool(last is not None and not last.online and self.is_cooling_down())
