"""Pembatas permintaan sederhana per alamat IP (jendela geser, di memori)."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_limiters = []


class _Window:
    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


def rate_limit(limit: int, window: float = 60.0):
    """Mengembalikan dependensi FastAPI yang menolak permintaan berlebih dengan 429."""
    limiter = _Window(limit, window)
    _limiters.append(limiter)

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(ip):
            raise HTTPException(
                status_code=429,
                detail="Terlalu banyak permintaan. Coba lagi sebentar.",
                headers={"Retry-After": str(int(window))},
            )

    return dependency


def reset_rate_limits() -> None:
    for limiter in _limiters:
        limiter.clear()
