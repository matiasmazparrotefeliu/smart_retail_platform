"""Verificación automática de esquema (Smart Retail Platform).

Se ejecuta en el arranque del contenedor (entrypoint.sh) y sincroniza el
esquema de la base de datos con los modelos ORM (`Base.metadata`), usando
la API de Alembic y `backend/alembic.ini`.

Flujo (el `upgrade head` va PRIMERO: Alembic exige que la BD esté en
`head` antes de permitir `revision --autogenerate`):

1. `alembic upgrade head` → aplica migraciones pendientes.
   Si la BD apunta a una revisión inexistente (alembic_version huérfano),
   ejecuta `alembic stamp head` y continúa: autogenerate reconstruirá
   las tablas faltantes.
2. `compare_metadata()` → compara los modelos contra el esquema real.
3. Sin diferencias → termina. Con diferencias → imprime el detalle,
   genera una migración con `alembic revision --autogenerate` y la
   aplica con `upgrade head`.

El resto de la lógica (imports de modelos, URL de BD, rutas) vive en
`migrations/env.py`, que Alembic ejecuta automáticamente al invocar
`command.revision` / `command.upgrade`.
"""

import sys
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.util import CommandError
from sqlalchemy import create_engine

# --- sys.path: raíz del repo y backend/ -----------------------------------
# Igual que en migrations/env.py: garantiza que los imports `src...` funcionen
# tanto en local (backend/ en el path) como en Docker (/app en el path).
BACKEND_DIR = Path(__file__).resolve().parent  # backend/ o /app en Docker
PROJECT_ROOT = BACKEND_DIR.parent              # raíz del repositorio
for path_ in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if path_ not in sys.path:
        sys.path.insert(0, path_)

# --- Configuración y modelos (mismo orden de imports que env.py) -----------
from src.core import config as app_config
from src.core.database import Base
from src.modules.tenant import models as tenant_models
from src.modules.auth import models as auth_models

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def _print_diffs(diffs: list) -> None:
    """Imprime en consola las diferencias detectadas por autogenerate."""
    print("Diferencias detectadas entre los modelos y la base de datos:")
    for diff in diffs:
        print(f"  - {diff}")


def _upgrade_head(cfg: Config) -> None:
    """Aplica migraciones pendientes (`upgrade head`).

    Si la BD quedó registrada en una revisión que ya no existe en
    `migrations/versions/` (alembic_version huérfano), recupera el arranque
    con `alembic stamp head`: la comparación posterior regenerará las tablas
    que falten vía autogenerate.
    """
    try:
        command.upgrade(cfg, "head")
    except CommandError as exc:
        if "Can't locate revision" not in str(exc):
            raise
        print(
            "ADVERTENCIA: la base de datos apunta a una revisión inexistente "
            "en migrations/versions/. Ejecutando 'alembic stamp head' para "
            "recuperarla; las tablas faltantes se regenerarán por autogenerate.",
            file=sys.stderr,
        )
        command.stamp(cfg, "head")


def _compare_with_db(engine) -> list:
    """Compara `Base.metadata` contra el esquema real de la base de datos."""
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        return compare_metadata(migration_context, Base.metadata)


def main() -> None:
    if not ALEMBIC_INI.exists():
        raise FileNotFoundError(f"No se encontró {ALEMBIC_INI}")

    db_url = app_config.settings.database_url
    if not db_url:
        db_url = "postgresql+psycopg://retail:retail@localhost:5432/retail"

    cfg = Config(str(ALEMBIC_INI))
    engine = create_engine(db_url)

    try:
        # 1. Dejar la BD en head (requisito para autogenerate).
        _upgrade_head(cfg)

        # 2. Detectar diferencias contra el esquema ya actualizado.
        diffs = _compare_with_db(engine)

        if diffs:
            _print_diffs(diffs)
            message = f"auto sync schema {datetime.now():%Y%m%d_%H%M%S}"
            print(f"Generando migración automática: '{message}'...")
            command.revision(cfg, autogenerate=True, message=message)
            print("Aplicando la migración generada (upgrade head)...")
            command.upgrade(cfg, "head")
        else:
            print("Sin diferencias entre los modelos y la base de datos.")

        print("Esquema de la base de datos sincronizado.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
