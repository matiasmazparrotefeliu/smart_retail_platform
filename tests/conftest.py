"""Configuración global de pytest para la suite de tests.

Responsabilidades:
- Añadir `backend/` al `sys.path` para resolver los imports `src...`.
- Redirigir la dependencia `get_db` hacia una base SQLite temporal
  (aislamiento total respecto a PostgreSQL de desarrollo/Docker).
- Exponer helpers de alto nivel:
  * `client`: TestClient de la app real con la DB de pruebas inyectada.
  * `db`: sesión de la DB de pruebas (para tests unitarios de servicios).
  * `dev_token`: lee el token de verificación impreso por el stub DEV de
    correo (stdout), SIN consultar la tabla `verification_tokens`.
  * `verified_admin`: registra, verifica y loguea un admin, devolviendo
    sus headers `Authorization: Bearer <JWT>` y datos básicos.
"""

import re
import sys
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Fuerza un motor SQLite ANTES de importar src.core.database: así la suite
# jamás toca PostgreSQL y no necesita el driver psycopg.
DB_PATH = Path(__file__).resolve().parent / ".test_auth.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{DB_PATH}")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base, get_db
from src.modules.auth.models import Role
from src.modules.auth.role_cache import clear as clear_role_cache
from main import app

# --- Base de datos de pruebas (SQLite por archivo, tmp del repo) -----------
engine = create_engine(
    f"sqlite+pysqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# La app usa SIEMPRE la DB de pruebas en esta suite
app.dependency_overrides[get_db] = _override_get_db

ROLES_BASE = ("tenant_admin", "analyst", "viewer")

# El stub DEV imprime: "[DEV] Correo de verificación para <email>: POST
# /api/v1/auth/verify con token: <uuid hex de 32 chars>"
_DEV_TOKEN_RE = re.compile(r"token: ([0-9a-f]{32})")


@pytest.fixture(autouse=True)
def _test_database():
    """Crea tablas + seed de roles antes de cada test; las borra al final."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    clear_role_cache()  # la DB se recrea: el cache de roles no puede sobrevivir
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    for role_name in ROLES_BASE:
        db.add(Role(name=role_name))
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP de integración contra la app con DB de pruebas."""
    return TestClient(app)


@pytest.fixture
def db():
    """Sesión de la DB de pruebas para tests unitarios de servicios."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def dev_token(capsys):
    """Lee el token de verificación del stdout (stub DEV de correo).

    El test de /verify NO necesita consultar la tabla verification_tokens:
    el token llega por el 'correo' (impresso en consola en desarrollo).
    """

    def _read() -> str:
        captured = capsys.readouterr()
        match = _DEV_TOKEN_RE.search(captured.out)
        assert match, "El stub DEV de correo no imprimió el token de verificación."
        return match.group(1)

    return _read


@pytest.fixture
def verified_admin(client, dev_token):
    """Factory: registra + verifica + loguea un admin y devuelve su contexto.

    Uso:
        admin = verified_admin("a@x.com", "Pwd12345!", "Corp A")
        -> {'id': 1, 'email': 'a@x.com', 'headers': {'Authorization': 'Bearer ...'}}
    """

    def _create(email: str, password: str, company: str = "Retail Test SA") -> dict:
        base = "/api/v1"

        register = client.post(
            f"{base}/auth/register",
            json={"company_name": company, "email": email, "password": password},
        )
        assert register.status_code == 201, register.json()

        verify = client.post(f"{base}/auth/verify", json={"token": dev_token()})
        assert verify.status_code == 200, verify.json()

        login = client.post(
            f"{base}/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.json()

        return {
            "id": register.json()["id"],
            "email": email,
            "company": company,
            "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        }

    return _create
