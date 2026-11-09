"""Tests de integración del módulo AUTH: endpoints /auth/*.

Matriz de validación:
- S-01: login antes de verificar → 403
- S-02: registro → verificación → login (happy path) → 200
- S-12: credenciales inválidas → 401
"""

BASE = "/api/v1"


def test_S01_login_denied_before_verify(client):
    """Un usuario recién registrado (sin verificar) no puede loguearse."""
    register = client.post(
        f"{BASE}/auth/register",
        json={"company_name": "Corp S01", "email": "s01@corp.com", "password": "Pwd12345!"},
    )
    assert register.status_code == 201
    assert register.json()["is_verified"] is False

    login = client.post(
        f"{BASE}/auth/login",
        json={"email": "s01@corp.com", "password": "Pwd12345!"},
    )
    assert login.status_code == 403


def test_S02_register_verify_login_happy_path(client, verified_admin):
    """El camino completo termina con un JWT emitido."""
    admin = verified_admin("s02@corp.com", "Pwd12345!", "Corp S02")
    assert admin["headers"]["Authorization"].startswith("Bearer ")


def test_S12_invalid_credentials_rejected(client, verified_admin):
    """Contraseña incorrecta → 401 con WWW-Authenticate."""
    admin = verified_admin("s12@corp.com", "Pwd12345!", "Corp S12")

    login = client.post(
        f"{BASE}/auth/login",
        json={"email": admin["email"], "password": "laQueNoEs"},
    )
    assert login.status_code == 401
    assert login.headers.get("www-authenticate") == "Bearer"
