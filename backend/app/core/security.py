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
VISITOR_WORKSPACE_CLAIM = "workspace_id"
SESSION_STARTED_CLAIM = "session_started_at"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class VisitorIdentity:
    subject: str
    workspace_id: int


@dataclass(frozen=True)
class RefreshIdentity:
    user_id: int
    session_started_at: datetime


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


def _create_token(
    user_id: int,
    token_type: str,
    expires_delta: timedelta,
    *,
    extra_claims: dict | None = None,
) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": secrets.token_urlsafe(16),
        "iat": issued_at,
        "exp": issued_at + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(user_id, ACCESS_TOKEN_TYPE, delta)


def refresh_token_lifetime(session_started_at: datetime) -> timedelta:
    """Sliding session lifetime: activity timeout bounded by the absolute ceiling.

    With ``SESSION_IDLE_TIMEOUT_MINUTES=0`` the refresh token keeps the fixed
    absolute ``REFRESH_TOKEN_EXPIRE_DAYS`` lifetime. Otherwise every refresh is
    re-issued with ``exp = min(now + idle, session_started_at + days)``, so a
    session dies ``idle`` after the last activity and never outlives the
    absolute ceiling measured from the first login.
    """
    settings = get_settings()
    idle = timedelta(minutes=settings.session_idle_timeout_minutes)
    ceiling = timedelta(days=settings.refresh_token_expire_days)
    if idle <= timedelta(0):
        return ceiling
    elapsed = datetime.now(timezone.utc) - session_started_at
    remaining_ceiling = ceiling - elapsed
    return max(timedelta(0), min(idle, remaining_ceiling))


def create_refresh_token(
    user_id: int,
    expires_delta: timedelta | None = None,
    *,
    session_started_at: datetime | None = None,
) -> str:
    started_at = session_started_at or datetime.now(timezone.utc)
    delta = expires_delta or refresh_token_lifetime(started_at)
    return _create_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        delta,
        extra_claims={SESSION_STARTED_CLAIM: int(started_at.timestamp())},
    )


def _decode_payload(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Invalid token type, expected {expected_type}")
    return payload


def _subject_user_id(payload: dict) -> int:
    subject = payload.get("sub")
    if subject is None:
        raise TokenError("Token is missing the subject")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenError("Token subject is not a valid user id") from exc


def decode_token(token: str, expected_type: str) -> int:
    return _subject_user_id(_decode_payload(token, expected_type))


def decode_refresh_token(token: str) -> RefreshIdentity:
    """Return the user and the original session start carried by a refresh token.

    Tokens issued before the claim existed fall back to ``iat``, so an in-flight
    session is not invalidated by the rollout.
    """
    payload = _decode_payload(token, REFRESH_TOKEN_TYPE)
    user_id = _subject_user_id(payload)
    started = payload.get(SESSION_STARTED_CLAIM, payload.get("iat"))
    if isinstance(started, (int, float)):
        session_started_at = datetime.fromtimestamp(started, tz=timezone.utc)
    else:
        session_started_at = datetime.now(timezone.utc)
    return RefreshIdentity(user_id=user_id, session_started_at=session_started_at)


def create_visitor_token(workspace_id: int, expires_delta: timedelta | None = None) -> str:
    issued_at = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(days=settings.visitor_token_expire_days)
    payload = {
        "sub": secrets.token_urlsafe(24),
        "type": VISITOR_TOKEN_TYPE,
        VISITOR_WORKSPACE_CLAIM: workspace_id,
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

    workspace_id = payload.get(VISITOR_WORKSPACE_CLAIM)
    if not isinstance(workspace_id, int):
        raise TokenError("Visitor token is missing the workspace")

    return VisitorIdentity(subject=str(subject), workspace_id=workspace_id)
