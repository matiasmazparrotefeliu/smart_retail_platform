"""Tests unitarios del módulo AUTH: lógica de negocio sin pasar por la API.

Cubre:
- Primitivas de seguridad (hashing de contraseñas y JWT).
- Reglas del AuthService (onboarding de empresa + admin).
- Reglas de la verificación de cuenta (expiración y uso único).
"""

from datetime import timedelta

import pytest

from src.core.datetime_utils import utc_now
from src.core.exceptions import InvalidRequestError
from src.core.security import (
    create_access_token,
    decode_access_token,
    get_hash_password,
    verify_password,
)
from src.modules.auth.models import VerificationToken
from src.modules.auth.schemas import UserRegister
from src.modules.auth.service import AuthService


# ---------------------------------------------------------------------------
# Primitivas de seguridad
# ---------------------------------------------------------------------------
def test_password_hash_roundtrip():
    """El hash nunca es la contraseña y las verificaciones son correctas."""
    hashed = get_hash_password("MiClave123!")

    assert hashed != "MiClave123!"
    assert verify_password("MiClave123!", hashed) is True
    assert verify_password("otra-clave", hashed) is False


def test_jwt_payload_carries_identity():
    """El JWT expone sub (user id), client_id y nombre del rol."""
    token = create_access_token({"sub": "1", "client_id": 7, "role": "analyst"})

    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["client_id"] == 7
    assert payload["role"] == "analyst"
    assert "exp" in payload and "iat" in payload


# ---------------------------------------------------------------------------
# AuthService: onboarding de empresa + admin
# ---------------------------------------------------------------------------
def test_register_creates_unverified_user_bound_to_new_client(db):
    """El admin nace vinculado a un client_id nuevo y sin verificar."""
    user = AuthService(db).register_company_and_admin(
        UserRegister(
            company_name="Corp Unit", email="unit@corp.com", password="Pwd12345!"
        )
    )

    assert user.id > 0
    assert user.client_id > 0
    assert user.is_verified is False
    assert user.is_active is True
    assert user.role.name == "tenant_admin"


def test_verify_account_rejects_expired_token(db):
    """Un token vencido no activa la cuenta (InvalidRequestError / 400)."""
    user = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Exp", email="exp@corp.com", password="Pwd12345!")
    )
    db.add(
        VerificationToken(
            user_id=user.id,
            token="tokenexpirado",
            expires_at=utc_now() - timedelta(hours=1),
        )
    )
    db.commit()

    with pytest.raises(InvalidRequestError) as exc:
        AuthService(db).verify_account("tokenexpirado")

    assert exc.value.status_code == 400


def test_verify_account_token_is_single_use(db):
    """El token válido activa una sola vez; el reuso falla (400)."""
    user = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Once", email="once@corp.com", password="Pwd12345!")
    )
    db.add(
        VerificationToken(
            user_id=user.id,
            token="tokensingle",
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    db.commit()

    service = AuthService(db)
    verified = service.verify_account("tokensingle")
    assert verified.is_verified is True

    with pytest.raises(InvalidRequestError) as exc:
        service.verify_account("tokensingle")
    assert exc.value.status_code == 400
