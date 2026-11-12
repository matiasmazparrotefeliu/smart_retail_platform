"""Dependencias de FastAPI para autenticación (JWT Bearer) y RBAC.

Expone:
- `get_current_user`: intercepta el header `Authorization: Bearer <token>`,
  decodifica/valida el JWT, carga al usuario y lo expone en la petición.
  El `client_id` del usuario queda disponible para inyectar el aislamiento
  multi-tenant en las consultas a la base de datos.
- `RoleChecker`: dependencia parametrizable que valida el rol del usuario
  (Control de Accesos basado en Roles).

Ejemplos:
    def mi_ruta(user: User = Depends(get_current_user)):
        ...  # filtrar con user.client_id

    @router.delete("/...", dependencies=[Depends(RoleChecker(["tenant_admin"]))])
    ...

Este módulo conoce FastAPI, los modelos y los repositorios, pero no
define rutas propias ni emite queries (el acceso a datos pasa por
`UserRepository`).
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.exceptions import ForbiddenActionError, UnauthorizedError
from src.core.security import decode_access_token
from src.modules.auth.models import User
from src.modules.auth.repositories import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
  """Extrae el token del header, lo valida y devuelve el usuario autenticado."""
  if credentials is None:
    raise UnauthorizedError(
        "Se requiere un token de acceso (Authorization: Bearer <token>).",
        headers={"WWW-Authenticate": "Bearer"},
    )

  # 1. Decodificar y verificar la firma y vigencia del JWT
  try:
    payload = decode_access_token(credentials.credentials)
  except JWTError:
    raise UnauthorizedError(
        "Token inválido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

  # 2. Localizar al usuario indicado en `sub`
  raw_user_id = payload.get("sub")
  try:
    user_id = int(raw_user_id) if raw_user_id is not None else None
  except (TypeError, ValueError):
    user_id = None

  if user_id is None:
    raise UnauthorizedError(
        "Token inválido: no contiene un usuario válido.",
        headers={"WWW-Authenticate": "Bearer"},
    )

  # El acceso a datos pasa por el repositorio (patrón Repository):
  # este módulo no emite queries propias.
  user = UserRepository(db).get_by_id(user_id)
  if not user:
    raise UnauthorizedError(
        "El usuario del token ya no existe.",
        headers={"WWW-Authenticate": "Bearer"},
    )

  # 3. Verificar que la cuenta siga activa y verificada
  if not user.is_active:
    raise ForbiddenActionError("La cuenta se encuentra desactivada.")
  if not user.is_verified:
    raise ForbiddenActionError("La cuenta no ha verificado su correo electrónico.")

  return user


class RoleChecker:
  """Dependencia de RBAC: permite la ruta solo a los roles indicados.

  Uso:
      Depends(RoleChecker(["tenant_admin"]))
  """

  def __init__(self, allowed_roles: list[str]):
    self.allowed_roles = allowed_roles

  def __call__(self, user: User = Depends(get_current_user)) -> User:
    role_name = user.role.name
    if role_name not in self.allowed_roles:
      raise ForbiddenActionError(
          "Acceso no autorizado: se requiere uno de los roles "
          f"{', '.join(self.allowed_roles)} (tu rol: {role_name}).",
      )
    return user
