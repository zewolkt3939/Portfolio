from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .models import AdminSession, AdminUser, LoginAttempt


SESSION_COOKIE = "portfolio_admin_session"
LOGIN_CSRF_COOKIE = "portfolio_login_csrf"
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_secret(value: str, settings: Settings | None = None) -> str:
    key = (settings or get_settings()).app_secret_key.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def encryption_box(settings: Settings | None = None) -> Fernet:
    cfg = settings or get_settings()
    key = cfg.field_encryption_key
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(cfg.app_secret_key.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_totp(secret: str, settings: Settings | None = None) -> str:
    return encryption_box(settings).encrypt(secret.encode()).decode()


def decrypt_totp(value: str, settings: Settings | None = None) -> str:
    try:
        return encryption_box(settings).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Không thể giải mã TOTP secret") from exc


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False


def get_client_ip(request: Request, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    if cfg.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def login_subjects(username: str, request: Request, settings: Settings | None = None) -> tuple[str, str]:
    return (
        hash_secret(f"account|{username.casefold()}", settings),
        hash_secret(f"ip|{get_client_ip(request, settings)}", settings),
    )


def login_is_limited(db: Session, subjects: str | tuple[str, ...], settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cfg.login_window_minutes)
    values = (subjects,) if isinstance(subjects, str) else subjects
    return any(
        (db.scalar(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.subject_hash == subject,
            LoginAttempt.successful.is_(False),
            LoginAttempt.attempted_at >= cutoff,
        )) or 0) >= cfg.login_attempt_limit
        for subject in values
    )


def record_login(db: Session, subjects: str | tuple[str, ...], successful: bool) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
    values = (subjects,) if isinstance(subjects, str) else subjects
    if successful:
        db.execute(delete(LoginAttempt).where(LoginAttempt.subject_hash.in_(values)))
    else:
        db.add_all(LoginAttempt(subject_hash=subject, successful=False) for subject in values)
    db.commit()


def create_session(db: Session, user: AdminUser, authenticated: bool, settings: Settings | None = None) -> tuple[str, AdminSession]:
    cfg = settings or get_settings()
    raw = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    session = AdminSession(
        user_id=user.id,
        token_hash=hash_secret(raw, cfg),
        authenticated=authenticated,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=cfg.session_absolute_days),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw, session


def load_session(db: Session, raw: str | None, require_authenticated: bool = True, settings: Settings | None = None) -> AdminSession | None:
    if not raw:
        return None
    cfg = settings or get_settings()
    item = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_secret(raw, cfg)))
    now = datetime.now(timezone.utc)
    idle_cutoff = now - timedelta(hours=cfg.session_idle_hours)
    expires_at = item.expires_at.replace(tzinfo=timezone.utc) if item and item.expires_at.tzinfo is None else (item.expires_at if item else None)
    last_seen_at = item.last_seen_at.replace(tzinfo=timezone.utc) if item and item.last_seen_at.tzinfo is None else (item.last_seen_at if item else None)
    if not item or expires_at < now or last_seen_at < idle_cutoff:
        if item:
            db.delete(item)
            db.commit()
        return None
    if require_authenticated and not item.authenticated:
        return None
    item.last_seen_at = now
    db.commit()
    return item


def csrf_token(raw_session: str, settings: Settings | None = None) -> str:
    return hash_secret("csrf|" + raw_session, settings)


def require_csrf(request: Request, raw_session: str, settings: Settings | None = None) -> None:
    supplied = request.headers.get("x-csrf-token")
    if not supplied:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thiếu CSRF token")
    if not hmac.compare_digest(supplied, csrf_token(raw_session, settings)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token không hợp lệ")


def verify_totp_or_recovery(db: Session, user: AdminUser, code: str, settings: Settings | None = None) -> bool:
    compact = code.strip().replace(" ", "").replace("-", "")
    secret = decrypt_totp(user.totp_secret_encrypted, settings)
    if compact.isdigit() and pyotp.TOTP(secret).verify(compact, valid_window=1):
        return True
    recovery = json.loads(user.recovery_codes_json or "[]")
    for index, encoded in enumerate(recovery):
        if verify_password(code.strip(), encoded):
            recovery.pop(index)
            user.recovery_codes_json = json.dumps(recovery)
            db.commit()
            return True
    return False


def require_admin(request: Request, db: Session) -> tuple[AdminUser, AdminSession, str]:
    raw = request.cookies.get(SESSION_COOKIE)
    session = load_session(db, raw)
    if not session or not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cần đăng nhập admin")
    return session.user, session, raw or ""
