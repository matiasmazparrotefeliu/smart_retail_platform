"""Primitivas de seguridad: hashing de contraseñas y JWT.

- Contraseñas: bcrypt vía passlib.
- Tokens: JWT firmados con `settings.secret_key` y `settings.algorithm`.

Este módulo no conoce FastAPI ni la base de datos: solo criptografía.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_hash_password(password: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash."""
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(data: dict[str, Any]) -> str:
    """Genera un JWT con `sub` (id de usuario), `role` y expiración."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": data.get("sub"),
        "client_id": data.get("client_id"),
        "role": data.get("role"),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT. Lanza `JWTError` si es inválido/expirado."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
