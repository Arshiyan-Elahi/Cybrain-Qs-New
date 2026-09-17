import time
from collections import defaultdict, deque

from app.core.config import get_settings
from app.core.errors import RateLimitedError


class SlidingWindowLimiter:
    """
    In-process sliding-window limiter for failed attempts.

    Deliberately simple. It protects a single instance, which is the common
    deployment today; **behind more than one worker or replica this must move
    to Redis**, since each process would otherwise keep its own counter. That
    is called out in the pre-production checklist rather than pretended away.
    """

    def __init__(self, max_attempts: int | None = None, window_seconds: int | None = None) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    @property
    def max_attempts(self) -> int:
        return self._max if self._max is not None else get_settings().login_max_attempts

    @property
    def window_seconds(self) -> int:
        return self._window if self._window is not None else get_settings().login_window_seconds

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        return hits

    def check(self, key: str) -> None:
        """Raise if this key has already exhausted its allowance."""
        hits = self._prune(key, time.monotonic())
        if len(hits) >= self.max_attempts:
            retry_after = int(self.window_seconds - (time.monotonic() - hits[0])) + 1
            raise RateLimitedError(
                "Too many failed attempts. Try again later.",
                details={"retryAfterSeconds": retry_after},
            )

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        """A success clears the record, so normal users are never penalised."""
        self._hits.pop(key, None)


login_rate_limiter = SlidingWindowLimiter()
