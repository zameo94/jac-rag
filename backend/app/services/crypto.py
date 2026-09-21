from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class CryptoError(Exception):
    pass


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise CryptoError("ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise CryptoError("Could not decrypt the stored secret") from exc
