"""Endpoint autentikasi admin: /api/auth/login, /logout, /session."""
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import (
    SESSION_COOKIE, SESSION_TTL_S, client_ip, get_session, login_limiter,
    require_admin, sessions, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login", summary="Login satu akun admin (dibatasi percobaan)")
def login(body: LoginRequest, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=503, detail="Login admin belum dikonfigurasi di server.")

    ip = client_ip(request)
    wait = login_limiter.retry_after(ip)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Terlalu banyak percobaan. Coba lagi dalam {wait} detik.",
            headers={"Retry-After": str(wait)},
        )

    # Kedua pemeriksaan selalu dijalankan agar waktu respons tidak membocorkan nama pengguna.
    user_ok = hmac.compare_digest(body.username.encode(), settings.ADMIN_USERNAME.encode())
    pass_ok = verify_password(body.password, settings.ADMIN_PASSWORD_HASH)
    if not (user_ok and pass_ok):
        login_limiter.fail(ip)
        raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")

    login_limiter.success(ip)
    sid, csrf = sessions.create(settings.ADMIN_USERNAME)
    response.set_cookie(
        key=SESSION_COOKIE, value=sid, max_age=SESSION_TTL_S, path="/",
        httponly=True, samesite="strict", secure=settings.COOKIE_SECURE,
    )
    return {"authenticated": True, "username": settings.ADMIN_USERNAME, "csrf_token": csrf}


@router.get("/session", summary="Status login pengunjung/admin")
def session_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    s = get_session(request)
    return {
        "authenticated": bool(s),
        "username": s["username"] if s else None,
        "csrf_token": s["csrf"] if s else None,
    }


@router.post("/logout", summary="Mengakhiri sesi")
def logout(response: Response, s: dict = Depends(require_admin)):
    sessions.delete(s["sid"])
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"authenticated": False}
