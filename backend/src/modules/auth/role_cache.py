"""Cache en memoria de la tabla `roles` (pequeña y casi estática).

Los roles casi nunca cambian, pero el sistema los consulta en cada
registro, alta de usuario y validación de permisos. Este cache evita
repetir `SELECT * FROM roles WHERE name = :name` constantemente.

Diseño:
- Cache a nivel de proceso: `dict[name, id]`. Guardamos el **id**, no el
  objeto ORM (los objetos FK/instancia están atados a una Session y
  compartirlos entre sesiones es frágil).
- Este módulo SOLO almacena: la carga en caso de miss (la query) vive
  en `RoleRepository`, que pasa su loader a `get_or_load`. Así el
  acceso a datos queda en la capa de repositorios y el cache es un
  detalle de infraestructura.
- `get_or_load(name, loader)`: devuelve el id cacheado; si no está,
  ejecuta `loader()` y cachea el resultado (también los Misses,
  evitando re-consulta inútil).
- `set_role_id(name, id)`: cuando alguien crea un rol nuevo, lo registra
  en el cache sin esperar la próxima consulta.
- `clear()`: invalidación manual (usada por los tests al recrear la DB).

La tabla es casi estática: si en el futuro se agregan endpoints de CRUD
de roles, recordar llamar `clear()` (o al menos la invalidación por rol)
al modificarlos.
"""

from collections.abc import Callable

# name -> id del rol; `None` significa "no existe en la DB" (miss cacheado)
_cache: dict[str, int | None] = {}


def get_or_load(name: str, loader: Callable[[], int | None]) -> int | None:
    """Devuelve el id del rol `name`; ejecuta `loader()` solo si no está cacheado."""
    if name not in _cache:
        _cache[name] = loader()
    return _cache[name]


def set_role_id(name: str, role_id: int) -> None:
    """Registra un rol recién creado en el cache."""
    _cache[name] = role_id


def clear() -> None:
    """Invalida toda la cache (recreación de DB, CRUD de roles, etc.)."""
    _cache.clear()
