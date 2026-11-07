"""Motor de base de datos y sesión SQLAlchemy.

Expone:
- `engine`: motor conectado a PostgreSQL vía `settings.database_url`.
- `SessionLocal`: fábrica de sesiones.
- `Base`: clase declarativa raíz para los modelos ORM (F2+).
- `get_db`: dependencia FastAPI que entrega una sesión por request.

Los modelos ORM se definen junto con Alembic.
"""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import settings

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)

class Base(DeclarativeBase):
    """Clase base declarativa de todos los modelos ORM."""

def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: abre una sesión y garantiza su cierre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
