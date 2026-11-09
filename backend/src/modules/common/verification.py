"""Emisión y envío de tokens de verificación de correo (lógica compartida).

Fuente ÚNICA de esta lógica: la usan `AuthService` (onboarding) y
`TenantService` (alta de usuarios operativos), eliminando la duplicación.

Invariantes:
- El token es un UUID hex de 32 caracteres, de un solo uso.
- Vigencia: `VERIFICATION_TOKEN_HOURS` (configuración centralizada aquí).
- `issue_verification_token` NO hace commit: el llamador controla la
  transacción (los servicios crean everything atómicamente).
- El formato del print del stub DEV es el "enlace de correo" en desarrollo;
  los tests lo leen del stdout (el formato es parte del contrato).
"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from src.core.datetime_utils import utc_now
from src.modules.auth.models import VerificationToken

# Vigencia del token de verificación de correo (horas)
VERIFICATION_TOKEN_HOURS = 24


def issue_verification_token(db: Session, user_id: int) -> str:
    """Crea el registro del token de verificación para un usuario.

    Agrega la fila a la sesión SIN hacer commit; devuelve el token en
    texto plano para construir el enlace de activación.
    """
    raw_token = uuid.uuid4().hex
    db.add(
        VerificationToken(
            user_id=user_id,
            token=raw_token,
            expires_at=utc_now() + timedelta(hours=VERIFICATION_TOKEN_HOURS),
        )
    )
    return raw_token


def send_verification_email(email: str, token: str) -> None:
    """Stub de envío de correo de activación.

    En desarrollo, registra el enlace por consola. Un proveedor SMTP real
    (Resend/Brevo/SES) reemplaza este stub sin tocar los servicios.
    """
    print(
        f"[DEV] Correo de verificación para {email}: "
        f"POST /api/v1/auth/verify con token: {token}"
    )
