"""In-memory rate limiting for the endpoints that attract abuse.

Sliding window per key (client IP, optionally + e-mail). It lives in the API process, which
is enough for the pilot (the production stack runs a single API process behind Caddy). A
multi-server deployment would move this to Redis or the database.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.config import get_settings


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: float, now: float | None = None) -> float:
        """Record a hit. Returns 0 if allowed, else the seconds until the next free slot."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_s:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window_s - now
            hits.append(now)
            return 0.0

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


WINDOW = SlidingWindow()


def client_ip(request: Request) -> str:
    # Behind Caddy, uvicorn --proxy-headers already puts the real client in request.client.
    return request.client.host if request.client else "desconhecido"


def rate_limit(name: str, limit: int, window_s: float) -> Callable[[Request], None]:
    """FastAPI dependency: at most `limit` calls per `window_s` seconds per client IP."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        wait = WINDOW.hit(f"{name}:{client_ip(request)}", limit, window_s)
        if wait > 0:
            minutes = max(1, round(wait / 60))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Muitas tentativas seguidas. Tente de novo em cerca de {minutes} minuto(s).",
                headers={"Retry-After": str(int(wait) + 1)},
            )

    return dependency
