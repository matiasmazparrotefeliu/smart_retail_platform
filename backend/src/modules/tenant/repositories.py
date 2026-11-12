"""Repositorios del módulo tenant.

Encapsulan el acceso a datos de las entidades que gestiona
`TenantService` (usuarios operativos y la empresa cliente), de modo
que el service NO contiene queries: solo reglas de negocio.

Convención (ver `src/core/repository.py`):
- Sin `commit()`/`rollback()` aquí: el service controla la transacción.
- Devuelven `Model | None`; interpretar `None` como error HTTP es del
  service (evita filtrar si un recurso no existe o no es del tenant).
"""

from src.modules.auth.models import User
from src.modules.auth.repositories import UserRepository as GlobalUserRepository
from src.modules.tenant.models import Client
from src.core.repository import BaseRepository, TenantScopedRepository


class TenantUserRepository(GlobalUserRepository, TenantScopedRepository[User]):
    """Usuarios del sistema, con lecturas acotadas al tenant del admin.

    Hereda de `GlobalUserRepository` el lookup global por email
    (`find_by_email`, necesario para validar la unicidad del alta) y de
    `TenantScopedRepository` las lecturas pre-filtradas por tenant
    (`for_tenant`, `get_tenant_entity`, `list_tenant_entities`).

    El MRO resuelve: `TenantUserRepository → GlobalUserRepository →
    TenantScopedRepository → BaseRepository[User]` (ambas cadenas
    convergen en la misma base parametrizada).
    """

    client_id_field = "client_id"    # default de la base; explícito por legibilidad
    order_by_field = "created_at"    # idem


class ClientRepository(BaseRepository[Client]):
    """Empresas cliente (tenants)."""

    model = Client

    def find_active_by_id(self, client_id: int) -> Client | None:
        """Recupera una empresa por PK solo si está activa.

        Combina existencia + vigencia en una sola consulta: un tenant
        inactivo no debe poder operar (dar altas de usuarios, etc.).
        """
        return (
            self.db.query(Client)
            .filter(Client.id == client_id, Client.is_active.is_(True))
            .first()
        )
