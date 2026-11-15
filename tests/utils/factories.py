"""Fábricas de datos para tests de integración entre módulos.

Funciones de soporte compartidas (NO fixtures: esos viven en
`conftest.py`). Están pensadas para reutilizarse desde los tests de
cualquier módulo (auth, tenant, catalog, scraping, ...).

Convención: hacen `assert` sobre los códigos de estado intermedios,
de modo que el test solo tenga que validar el comportamiento objetivo.
"""

from fastapi.testclient import TestClient


def create_product(
    client: TestClient, headers: dict, payload: dict, **overrides
) -> dict:
    """Da de alta un producto en el catálogo; devuelve el body de la 201.

    `payload` es el dict base del test; `overrides` permite variar
    campos individuales (ej. sku para evitar colisiones).
    """
    body = {**payload, **overrides}
    response = client.post("/api/v1/catalog/products", json=body, headers=headers)
    assert response.status_code == 201, response.json()
    return response.json()


def create_operational_user(
    client: TestClient, admin: dict, email: str, role_name: str, dev_token
) -> dict:
    """Registra, verifica y loguea un usuario operativo de un tenant.

    Devuelve `{"headers": {...Authorization Bearer...}}`, el formato que
    consumen los demás helpers y assertions de headers.
    """
    created = client.post(
        "/api/v1/tenants/users",
        json={"email": email, "password": "Pwd12345!", "role_name": role_name},
        headers=admin["headers"],
    )
    assert created.status_code == 201, created.json()

    verify = client.post("/api/v1/auth/verify", json={"token": dev_token()})
    assert verify.status_code == 200, verify.json()

    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Pwd12345!"}
    )
    assert login.status_code == 200, login.json()
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}
