"""Cache en memoria de la tabla `roles` (pequeña y casi estática).

Los roles casi nunca cambian, pero el sistema los consulta en cada
registro, alta de usuario y validación de permisos. Este cache evita
repetir `SELECT * FROM roles WHERE name = :name` constantemente.

Diseño:
- Cache a nivel de proceso: `dict[name, id]`. Guardamos el **id**, no el
  objeto ORM (los objetos FK/instancia están atados a una Session y
  compartirlos entre sesiones es frágil).
- `get_role_id(db, name)`: primero cache; si no está, consulta la DB y
  cachea el resultado (también los Misses, evitando re-consulta inútil).
- `set_role_id(name, id)`: cuando alguien crea un rol nuevo, lo registra
  en el cache sin esperar la próxima consulta.
- `clear()`: invalidación manual (usada por los tests al recrear la DB).

La tabla es casi estática: si en el futuro se agregan endpoints de CRUD
de roles, recordar llamar `clear()` (o al menos la invalidación por rol)
al modificarlos.
"""

from sqlalchemy.orm import Session

from src.modules.auth.models import Role

# name -> id del rol; `None` significa "no existe en la DB" (miss cacheado)
_cache: dict[str, int | None] = {}


def get_role_id(db: Session, name: str) -> int | None:
    """Devuelve el id del rol `name`; consulta la DB solo si no está cacheado."""
    if name not in _cache:
        role = db.query(Role).filter(Role.name == name).first()
        _cache[name] = role.id if role else None
    return _cache[name]


def set_role_id(name: str, role_id: int) -> None:
    """Registra un rol recién creado en el cache."""
    _cache[name] = role_id


def clear() -> None:
    """Invalida toda la cache (recreación de DB, CRUD de roles, etc.)."""
    _cache.clear()
