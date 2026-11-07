"""Entorno de Alembic.

Sincroniza `target_metadata` con los metadatos de los modelos ORM
(`Base.metadata`) y toma la URL de la base de datos desde
`settings.database_url` (backend/src/core/config.py), respetando las
variables de entorno y el `.env` de la raíz del repositorio.

Ejecutar Alembic desde la raíz del repositorio:
    alembic revision --autogenerate -m "..."
    alembic upgrade head
"""

import sys
import types
from importlib.util import find_spec
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- sys.path: raíz del repo y backend/ ----------------------------------
# Local:  los modelos viven en `<raíz>/backend` y se importan como
#         `src...` (con la raíz del repo en sys.path).
# Docker: la copia del backend está directamente en la raíz (`/app`), por lo
#         que se registra un namespace package `backend` apuntando a esa
#         raíz y así los imports `src...` siguen funcionando
#         sin cambios en el código.
BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/migrations → backend/
PROJECT_ROOT = BACKEND_DIR.parent                  # raíz del repositorio / /app en Docker
for path_ in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if path_ not in sys.path:
        sys.path.insert(0, path_)

if find_spec("backend") is None:
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(BACKEND_DIR)]
    sys.modules["backend"] = backend_pkg

# --- Configuración del logging -------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Importación de la app y de TODOS los modelos -------------------------
# Importarlos aquí garantiza que queden registrados en Base.metadata,
# imprescindible para que `alembic revision --autogenerate` los detecte.
from src.core import config as app_config
from src.core.database import Base
from src.modules.tenant import models as tenant_models
from src.modules.auth import models as auth_models

target_metadata = Base.metadata

# --- URL de la base de datos ---------------------------------------------
# Prioridad: variable DATABASE_URL (entorno/.env) → valor por defecto.
db_url = app_config.settings.database_url
if not db_url:
    db_url = "postgresql+psycopg://retail:retail@localhost:5432/retail"
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Genera SQL para `alembic upgrade --sql` sin conectar a la BD."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones conectándose al motor real."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
