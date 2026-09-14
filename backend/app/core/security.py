from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import SecurityError


def _get_fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise SecurityError("TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise SecurityError("Failed to decrypt token") from exc
