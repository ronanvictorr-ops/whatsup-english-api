import math
import os
from collections import deque
from threading import RLock
from time import monotonic
from typing import Callable

from fastapi import HTTPException, Request


class SlidingWindowRateLimiter:
    def __init__(self, clock: Callable[[], float] = monotonic, max_keys: int = 10_000):
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = RLock()

    def check(
        self,
        scope: str,
        identifier: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate limit and window must be positive")

        now = self._clock()
        key = f"{scope}:{identifier}"
        cutoff = now - window_seconds

        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Muitas tentativas. Aguarde um pouco e tente novamente.",
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)
            if len(self._events) > self._max_keys:
                self._discard_inactive(cutoff)

    def _discard_inactive(self, cutoff: float) -> None:
        inactive = [
            key
            for key, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for key in inactive:
            self._events.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = SlidingWindowRateLimiter()


def _configured_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def enforce_rate_limit(
    scope: str,
    identifier: str,
    default_limit: int,
    default_window_seconds: int,
) -> None:
    if os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() != "true":
        return

    setting_prefix = f"RATE_LIMIT_{scope.upper()}"
    limiter.check(
        scope=scope,
        identifier=identifier or "unknown",
        limit=_configured_int(f"{setting_prefix}_REQUESTS", default_limit),
        window_seconds=_configured_int(
            f"{setting_prefix}_WINDOW_SECONDS",
            default_window_seconds,
        ),
    )


def client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # The edge proxy appends the address it observed. Using the final value
        # prevents callers from bypassing the limit with a forged first entry.
        candidate = forwarded_for.split(",")[-1].strip()
        if candidate:
            return candidate

    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"
