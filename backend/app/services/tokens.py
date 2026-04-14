from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _cipher() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise RuntimeError(
            "FERNET_KEY is not set. Generate one: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(key.encode("utf-8"))


def encrypt(token: str) -> str:
    return _cipher().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
