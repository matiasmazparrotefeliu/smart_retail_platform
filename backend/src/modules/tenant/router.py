"""Rutas del módulo tenant: gestión de usuarios operativos de la empresa.

Todos los endpoints están protegidos en doble capa:
1. `get_current_user`  → exige un JWT válido (identidad autenticada).
2. `RoleChecker(["tenant_admin"])` → exige rol de administrador del tenant.

El `client_id` SIEMPRE proviene del token del admin autenticado;
nunca del body de la petición (aislamiento multi-tenant).

Nota transitoria (patrón Repository): el acceso a datos vive en los
repositorios (`src/modules/tenant/repositories.py`, inyectados vía
`Depends()`). Los endpoints aún pasan `db` al service porque los tests
existen construyendo `TenantService(db)`; cuando se actualicen, la
sesión dejará de viajar al service por la firma.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.core.auth_handler import RoleChecker
from src.core.database import get_db
from src.modules.auth.models import User
from src.modules.tenant.repositories import (
    ClientRepository,
    TenantUserRepository,
)
from src.modules.tenant.schemas import UserCreateTenant, UserResetPassword, UserTenantResponse, UserUpdateTenant
from src.modules.tenant.service import TenantService

_admin_only = RoleChecker(["tenant_admin"])


def get_user_repository(db: Session = Depends(get_db)) -> TenantUserRepository:
    """Inyecta el repositorio de usuarios ligado a la sesión del request.

    Devuelve `TenantUserRepository` (lecturas acotadas por tenant); el
    lookup global por email se hereda de `auth.repositories.UserRepository`.
    """
    return TenantUserRepository(db)


def get_client_repository(db: Session = Depends(get_db)) -> ClientRepository:
    """Inyecta el repositorio de empresas ligado a la sesión del request."""
    return ClientRepository(db)


class TenantRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/tenants", tags=["Gestión de Empresa"])

        # Registro de rutas usando add_api_route en el constructor
        self.router.add_api_route(
            path="/users",
            endpoint=self.create_user,
            methods=["POST"],
            response_model=UserTenantResponse,
            status_code=status.HTTP_201_CREATED,
            summary="El admin registra un usuario operativo (analyst/viewer) de SU empresa.",
        )

        self.router.add_api_route(
            path="/users",
            endpoint=self.list_users,
            methods=["GET"],
            response_model=list[UserTenantResponse],
            summary="Lista todos los usuarios de la empresa del admin autenticado.",
        )

        self.router.add_api_route(
            path="/users/{user_id}",
            endpoint=self.update_user,
            methods=["PATCH"],
            response_model=UserTenantResponse,
            summary="Actualiza rol y/o estado de un usuario del propio tenant.",
        )

        self.router.add_api_route(
            path="/users/{user_id}/password",
            endpoint=self.reset_password,
            methods=["POST"],
            response_model=UserTenantResponse,
            summary="Resetea la contraseña de un usuario del propio tenant.",
        )

    def create_user(
        self,
        data: UserCreateTenant,
        db: Session = Depends(get_db),
        users: TenantUserRepository = Depends(get_user_repository),
        clients: ClientRepository = Depends(get_client_repository),
        admin: User = Depends(_admin_only),
    ):
        """El admin registra un usuario operativo (analyst/viewer) de SU empresa."""
        service = TenantService(db, users=users, clients=clients)
        return service.create_tenant_user(admin_client_id=admin.client_id, data=data)

    def list_users(
        self,
        db: Session = Depends(get_db),
        users: TenantUserRepository = Depends(get_user_repository),
        clients: ClientRepository = Depends(get_client_repository),
        admin: User = Depends(_admin_only),
    ):
        """Lista todos los usuarios de la empresa del admin autenticado."""
        service = TenantService(db, users=users, clients=clients)
        return service.list_tenant_users(admin.client_id)

    def update_user(
        self,
        user_id: int,
        data: UserUpdateTenant,
        db: Session = Depends(get_db),
        users: TenantUserRepository = Depends(get_user_repository),
        clients: ClientRepository = Depends(get_client_repository),
        admin: User = Depends(_admin_only),
    ):
        """Actualiza rol y/o estado de un usuario del propio tenant."""
        service = TenantService(db, users=users, clients=clients)
        return service.update_tenant_user(
            admin_client_id=admin.client_id, user_id=user_id, data=data
        )

    def reset_password(
        self,
        user_id: int,
        data: UserResetPassword,
        db: Session = Depends(get_db),
        users: TenantUserRepository = Depends(get_user_repository),
        clients: ClientRepository = Depends(get_client_repository),
        admin: User = Depends(_admin_only),
    ):
        """Resetea la contraseña de un usuario del propio tenant."""
        service = TenantService(db, users=users, clients=clients)
        return service.reset_tenant_user_password(
            admin_client_id=admin.client_id, user_id=user_id, data=data
        )