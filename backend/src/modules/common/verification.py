"""Envío de tokens de verificación de correo (stub compartido).

Fuente ÚNICA de esta lógica: la usan `AuthService` (onboarding) y
`TenantService` (alta de usuarios operativos), eliminando la duplicación.

La EMISIÓN del token vive en `VerificationTokenRepository`
(`create_for_user`): es acceso a datos y por eso pertenece a la capa de
repositorios (ver `src/modules/auth/repositories.py`, constante
`VERIFICATION_TOKEN_HOURS`). Este módulo queda solo con la entrega del
"correo".

Invariantes:
- El token es un UUID hex de 32 caracteres, de un solo uso, con vigencia
  de `VERIFICATION_TOKEN_HOURS` (configurado en el repositorio).
- El formato del print del stub DEV es el "enlace de correo" en
  desarrollo; los tests lo leen del stdout (el formato es parte del
  contrato, NO cambiarlo).
"""


def send_verification_email(email: str, token: str) -> None:
    """Stub de envío de correo de activación.

    En desarrollo, registra el enlace por consola. Un proveedor SMTP real
    (Resend/Brevo/SES) reemplaza este stub sin tocar los servicios ni los
    repositorios.
    """
    print(
        f"[DEV] Correo de verificación para {email}: "
        f"POST /api/v1/auth/verify con token: {token}"
    )
