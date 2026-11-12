"""Repositorios del módulo auth.

Encapsulan el acceso a datos de `AuthService` (y del lookup de roles
compartido con `TenantService`), de modo que los services NO contienen
queries: solo reglas de negocio.

Convención (ver `src/core/repository.py`):
- Sin `commit()`/`rollback()` aquí: el service controla la transacción
  (crítico en `register_company_and_admin`, que es una transacción
  multi-entidad: role + client + user + token).
- Devuelven `Model | None`; interpretar `None` como error HTTP es del
  service (evita filtrar si un recurso no existe o no es válido).
"""

import uuid
from datetime import timedelta

from src.core.datetime_utils import utc_now
from src.core.repository import BaseRepository
from src.modules.auth.models import Role, User, VerificationToken
from src.modules.auth.role_cache import get_or_load, set_role_id

# Vigencia del token de verificación de correo (horas)
VERIFICATION_TOKEN_HOURS = 24


class RoleRepository(BaseRepository[Role]):
    """Roles del sistema (RBAC), con lookup por nombre cacheado a nivel proceso."""

    model = Role

    def find_by_name(self, name: str) -> Role | None:
        """Lookup crudo por nombre (sin cache)."""
        return self.db.query(Role).filter(Role.name == name).first()

    def find_id_by_name(self, name: str) -> int | None:
        """Id del rol `name`; consulta la DB solo si no está cacheado.

        Cachea también los misses (`None`): un rol inexistente no fuerza
        una re-consulta en cada request. Ver `role_cache.get_or_load`.
        """
        return get_or_load(name, lambda: self._load_role_id(name))

    def find_by_name_cached(self, name: str) -> Role | None:
        """Objeto Role por nombre, con el mismo cache de `find_id_by_name`.

        La recuperación del objeto por PK aprovecha el identity-map de la
        sesión (sin query si ya está cargada). `None` también puede
        significar "cacheado como inexistente".
        """
        role_id = self.find_id_by_name(name)
        if role_id is None:  # miss cacheado: el rol no existe
            return None
        return self.db.get(Role, role_id)  # None si la DB cambió bajo los pies del cache

    def get_or_create(self, name: str, description: str | None = None) -> Role:
        """Recupera el rol `name` o lo crea si no existe (bootstrap).

        Se usa en el onboarding para garantizar el rol 'tenant_admin'.
        Si crea, registra el id en el cache inmediatamente.
        """
        role = self.find_by_name_cached(name)
        if role is not None:
            return role
        role = self.add(Role(name=name, description=description))
        set_role_id(name, role.id)
        return role

    def _load_role_id(self, name: str) -> int | None:
        """Loader para el cache: id del rol, o None si no existe."""
        role = self.find_by_name(name)
        return role.id if role else None


class UserRepository(BaseRepository[User]):
    """Usuarios del sistema. Lookup GLOBAL por email (sin scope de tenant).

    Es global a propósito: el login y la unicidad del alta suceden ANTES
    de conocer el tenant del usuario, así que aquí no aplica el
    aislamiento por `client_id`. Las lecturas ACOTADAS al tenant viven
    en `TenantUserRepository` (`src/modules/tenant/repositories.py`),
    que hereda de esta clase.
    """

    model = User

    def find_by_email(self, email: str) -> User | None:
        """Busca por correo con unicidad global."""
        return self.db.query(User).filter(User.email == email).first()


class VerificationTokenRepository(BaseRepository[VerificationToken]):
    """Tokens de verificación de correo (un solo uso, vigencia limitada)."""

    model = VerificationToken

    def create_for_user(self, user_id: int) -> str:
        """Crea el registro del token de verificación de un usuario.

        Agrega la fila a la sesión SIN hacer commit: el service la
        confirma junto con el resto de la transacción. Devuelve el token
        en texto plano para construir el enlace de activación.
        """
        raw_token = uuid.uuid4().hex
        self.add(
            VerificationToken(
                user_id=user_id,
                token=raw_token,
                expires_at=utc_now() + timedelta(hours=VERIFICATION_TOKEN_HOURS),
            )
        )
        return raw_token

    def find_by_token(self, token: str) -> VerificationToken | None:
        """Recupera el registro del token plano. La expiración la valida el service."""
        return (
            self.db.query(VerificationToken)
            .filter(VerificationToken.token == token)
            .first()
        )
