import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
VISITOR_TOKEN_TYPE = "visitor"
VISITOR_TENANT_CLAIM = "tenant_id"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class VisitorIdentity:
    subject: str
    tenant_id: int


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return password_context.verify(plain_password, password_hash)


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


EMBED_KEY_PREFIX = "jrk_"
EMBED_KEY_PREFIX_LENGTH = 12


def generate_embed_key() -> str:
    return f"{EMBED_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def embed_key_prefix(key: str) -> str:
    return key[:EMBED_KEY_PREFIX_LENGTH]


def _create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": secrets.token_urlsafe(16),
        "iat": issued_at,
        "exp": issued_at + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(user_id, ACCESS_TOKEN_TYPE, delta)


def create_refresh_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(days=settings.refresh_token_expire_days)
    return _create_token(user_id, REFRESH_TOKEN_TYPE, delta)


def decode_token(token: str, expected_type: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Invalid token type, expected {expected_type}")

    subject = payload.get("sub")
    if subject is None:
        raise TokenError("Token is missing the subject")

    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenError("Token subject is not a valid user id") from exc


def create_visitor_token(tenant_id: int, expires_delta: timedelta | None = None) -> str:
    issued_at = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(days=settings.visitor_token_expire_days)
    payload = {
        "sub": secrets.token_urlsafe(24),
        "type": VISITOR_TOKEN_TYPE,
        VISITOR_TENANT_CLAIM: tenant_id,
        "jti": secrets.token_urlsafe(16),
        "iat": issued_at,
        "exp": issued_at + delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_visitor_token(token: str) -> VisitorIdentity:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired visitor token") from exc

    if payload.get("type") != VISITOR_TOKEN_TYPE:
        raise TokenError("Invalid token type, expected visitor")

    subject = payload.get("sub")
    if not subject:
        raise TokenError("Visitor token is missing the subject")

    tenant_id = payload.get(VISITOR_TENANT_CLAIM)
    if not isinstance(tenant_id, int):
        raise TokenError("Visitor token is missing the tenant")

    return VisitorIdentity(subject=str(subject), tenant_id=tenant_id)
