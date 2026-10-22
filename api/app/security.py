import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(user_id: int, role: str, token_version: int = 0) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_tracking_token() -> tuple[str, str]:
    """Return (token, sha256 hex). Only the hash is stored."""
    token = secrets.token_urlsafe(24)
    return token, hash_tracking_token(token)


def hash_tracking_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tracking_token_matches(token: str | None, stored_hash: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(hash_tracking_token(token), stored_hash)
