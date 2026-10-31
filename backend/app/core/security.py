"""Autentikasi admin: hash kata sandi, sesi di memori server, token CSRF, dan pembatasan login."""
import hashlib
import hmac
import secrets
import threading
import time
from typing import Dict, Optional

from fastapi import HTTPException, Request

SESSION_COOKIE = "wsn_session"
SESSION_TTL_S = 12 * 3600
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_S = 300

_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        expected_b = bytes.fromhex(expected)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                            n=int(n), r=int(r), p=int(p), dklen=len(expected_b))
        return hmac.compare_digest(dk, expected_b)
    except (ValueError, TypeError):
        return False


class _Sessions:
    """Sesi disimpan di memori: logout benar-benar mencabut sesi, dan restart server mengakhiri semua sesi."""

    def __init__(self) -> None:
        self._data: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, username: str):
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            for k in [k for k, v in self._data.items() if v["expires"] < now]:
                del self._data[k]
            self._data[sid] = {"username": username, "csrf": csrf, "expires": now + SESSION_TTL_S}
        return sid, csrf

    def get(self, sid: str) -> Optional[dict]:
        with self._lock:
            s = self._data.get(sid)
            if not s:
                return None
            if s["expires"] < time.time():
                del self._data[sid]
                return None
            return {**s, "sid": sid}

    def delete(self, sid: str) -> None:
        with self._lock:
            self._data.pop(sid, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class _LoginLimiter:
    """5 percobaan salah dari satu alamat IP, lalu dikunci 5 menit."""

    def __init__(self) -> None:
        self._data: Dict[str, list] = {}
        self._lock = threading.Lock()

    def retry_after(self, ip: str) -> int:
        now = time.time()
        with self._lock:
            rec = self._data.get(ip)
            if not rec:
                return 0
            if rec[1] > now:
                return int(rec[1] - now) + 1
            if rec[1]:
                del self._data[ip]
            return 0

    def fail(self, ip: str) -> None:
        with self._lock:
            rec = self._data.setdefault(ip, [0, 0.0])
            rec[0] += 1
            if rec[0] >= LOGIN_MAX_FAILS:
                rec[0], rec[1] = 0, time.time() + LOGIN_LOCK_S

    def success(self, ip: str) -> None:
        with self._lock:
            self._data.pop(ip, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


sessions = _Sessions()
login_limiter = _LoginLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_session(request: Request) -> Optional[dict]:
    sid = request.cookies.get(SESSION_COOKIE)
    return sessions.get(sid) if sid else None


def require_admin(request: Request) -> dict:
    """Dependensi endpoint admin. Permintaan yang mengubah data wajib membawa token CSRF."""
    s = get_session(request)
    if not s:
        raise HTTPException(status_code=401, detail="Perlu login admin.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token.encode(), s["csrf"].encode()):
            raise HTTPException(status_code=403, detail="Token CSRF tidak valid.")
    return s
