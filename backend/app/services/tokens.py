from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _cipher() -> Fernet:
    return Fernet(get_settings().fernet_key.encode("utf-8"))


def encrypt(token: str) -> str:
    return _cipher().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
