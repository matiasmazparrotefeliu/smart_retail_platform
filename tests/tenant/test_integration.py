"""Tests de integración del módulo TENANT: endpoints /tenants/user*.

Incluye además los cases de seguridad que atacan esta Superficie protegida:
- S-03: admin crea analyst → 201
- S-04: admin intenta crear otro admin → 403
- S-05: rol inexistente → 400
- S-06: email duplicado en tenant → 409
- S-07: analyst bloqueado por RBAC (crear/listar) → 403
- S-08: cambio de rol + reset de contraseña → login con nueva clave
- S-09: aislamiento cross-tenant → 404
- S-10: petición sin token → 401
- S-11: token manipulado → 401
"""

BASE = "/api/v1"


# ---------------------------------------------------------------------------
# Alta de usuarios operativos (el admin gestiona su equipo)
# ---------------------------------------------------------------------------
def test_S03_admin_creates_analyst(client, verified_admin):
    """El admin registra un usuario operativo de su propia empresa."""
    admin = verified_admin("s03admin@corp.com", "Pwd12345!", "Corp S03")

    response = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s03user@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role_name"] == "analyst"
    assert body["is_verified"] is False
    assert body["is_active"] is True


def test_S04_admin_cannot_create_second_admin(client, verified_admin):
    """Regla de oro: un solo admin por empresa."""
    admin = verified_admin("s04admin@corp.com", "Pwd12345!", "Corp S04")

    response = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s04admin2@corp.com", "password": "Pwd12345!", "role_name": "tenant_admin"},
        headers=admin["headers"],
    )
    assert response.status_code == 403
    assert "administrador" in response.json()["detail"].lower()


def test_S05_unknown_role_rejected(client, verified_admin):
    """Roles fuera de {analyst, viewer} no permiten el alta (400)."""
    admin = verified_admin("s05admin@corp.com", "Pwd12345!", "Corp S05")

    response = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s05user@corp.com", "password": "Pwd12345!", "role_name": "ghost"},
        headers=admin["headers"],
    )
    assert response.status_code == 400


def test_S06_duplicate_email_conflict(client, verified_admin):
    """El correo ya registrado bloquea un segundo alta (409)."""
    admin = verified_admin("s06admin@corp.com", "Pwd12345!", "Corp S06")

    first = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s06user@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin["headers"],
    )
    assert first.status_code == 201

    second = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s06user@corp.com", "password": "Pwd12345!", "role_name": "viewer"},
        headers=admin["headers"],
    )
    assert second.status_code == 409


def test_list_users_returns_tenant_team(client, verified_admin):
    """El admin ve a su equipo completo tras dar de alta usuarios."""
    admin = verified_admin("listadmin@corp.com", "Pwd12345!", "Corp List")

    client.post(
        f"{BASE}/tenants/users",
        json={"email": "a@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin["headers"],
    )
    client.post(
        f"{BASE}/tenants/users",
        json={"email": "b@corp.com", "password": "Pwd12345!", "role_name": "viewer"},
        headers=admin["headers"],
    )

    listing = client.get(f"{BASE}/tenants/users", headers=admin["headers"])
    assert listing.status_code == 200
    emails = sorted(u["email"] for u in listing.json())
    assert emails == [
        "a@corp.com",
        "b@corp.com",
        "listadmin@corp.com",
    ]


# ---------------------------------------------------------------------------
# Ciclo de vida: rol y contraseña
# ---------------------------------------------------------------------------
def test_S08_role_change_and_password_reset(client, verified_admin, dev_token):
    """El admin cambia el rol y resetea la contraseña; la clave vieja muere."""
    admin = verified_admin("s08admin@corp.com", "Pwd12345!", "Corp S08")

    created = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s08user@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin["headers"],
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    # Token de verificación del usuario operativo (llega por correo DEV)
    user_token = dev_token()

    promote = client.patch(
        f"{BASE}/tenants/users/{user_id}",
        json={"role_name": "viewer"},
        headers=admin["headers"],
    )
    assert promote.status_code == 200
    assert promote.json()["role_name"] == "viewer"

    reset = client.post(
        f"{BASE}/tenants/users/{user_id}/password",
        json={"new_password": "ClaveNueva99!"},
        headers=admin["headers"],
    )
    assert reset.status_code == 200

    # La contraseña vieja ya no sirve (credenciales inválidas → 401)
    old_login = client.post(
        f"{BASE}/auth/login",
        json={"email": "s08user@corp.com", "password": "Pwd12345!"},
    )
    assert old_login.status_code == 401

    # Sin verificar el correo, el acceso sigue bloqueado (403)
    blocked = client.post(
        f"{BASE}/auth/login",
        json={"email": "s08user@corp.com", "password": "ClaveNueva99!"},
    )
    assert blocked.status_code == 403

    # El usuario verifica su correo y ahora sí ingresa con la nueva clave
    activate = client.post(f"{BASE}/auth/verify", json={"token": user_token})
    assert activate.status_code == 200

    new_login = client.post(
        f"{BASE}/auth/login",
        json={"email": "s08user@corp.com", "password": "ClaveNueva99!"},
    )
    assert new_login.status_code == 200


# ---------------------------------------------------------------------------
# Nivel C: seguridad (RBAC y aislamiento)
# ---------------------------------------------------------------------------
def test_S07_analyst_blocked_by_rbac(client, verified_admin, dev_token):
    """Un analyst no puede crear ni listar usuarios (403)."""
    admin = verified_admin("s07admin@corp.com", "Pwd12345!", "Corp S07")

    created = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s07user@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin["headers"],
    )
    assert created.status_code == 201

    # Activar y loguear al analyst: el token llega por el 'correo' DEV
    analyst_token = dev_token()
    verify = client.post(f"{BASE}/auth/verify", json={"token": analyst_token})
    assert verify.status_code == 200
    analyst_login = client.post(
        f"{BASE}/auth/login",
        json={"email": "s07user@corp.com", "password": "Pwd12345!"},
    )
    assert analyst_login.status_code == 200
    analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}

    create_other = client.post(
        f"{BASE}/tenants/users",
        json={"email": "otro@corp.com", "password": "Pwd12345!", "role_name": "viewer"},
        headers=analyst_headers,
    )
    assert create_other.status_code == 403

    list_users = client.get(f"{BASE}/tenants/users", headers=analyst_headers)
    assert list_users.status_code == 403


def test_S09_cross_tenant_isolation(client, verified_admin):
    """El admin B no puede gestionar ni ver usuarios del tenant A."""
    admin_a = verified_admin("s09a@corp.com", "Pwd12345!", "Corp A")
    admin_b = verified_admin("s09b@corp.com", "Pwd12345!", "Corp B")

    created = client.post(
        f"{BASE}/tenants/users",
        json={"email": "s09user@corp.com", "password": "Pwd12345!", "role_name": "analyst"},
        headers=admin_a["headers"],
    )
    assert created.status_code == 201
    victim_id = created.json()["id"]

    patch_by_b = client.patch(
        f"{BASE}/tenants/users/{victim_id}",
        json={"is_active": False},
        headers=admin_b["headers"],
    )
    assert patch_by_b.status_code == 404

    list_by_b = client.get(f"{BASE}/tenants/users", headers=admin_b["headers"])
    emails_of_b = [u["email"] for u in list_by_b.json()]
    assert "s09user@corp.com" not in emails_of_b


def test_S10_missing_token_unauthorized(client):
    """Sin credenciales no hay acceso al panel del tenant (401)."""
    response = client.get(f"{BASE}/tenants/users")
    assert response.status_code == 401


def test_S11_tampered_token_rejected(client, verified_admin):
    """Un JWT alterado invalida la firma y se rechaza (401)."""
    admin = verified_admin("s11@corp.com", "Pwd12345!", "Corp S11")

    raw = admin["headers"]["Authorization"].split(" ")[1]
    tampered = raw[:-2] + "xx"

    response = client.get(
        f"{BASE}/tenants/users",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert response.status_code == 401
