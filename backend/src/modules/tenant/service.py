from sqlalchemy.orm import Session

from src.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ForbiddenActionError,
    InvalidRequestError,
)
from src.core.security import get_hash_password
from src.modules.auth.models import Role, User
from src.modules.auth.repositories import RoleRepository, VerificationTokenRepository
from src.modules.common.verification import send_verification_email
from src.modules.tenant.repositories import (
    ClientRepository,
    TenantUserRepository,
)
from src.modules.tenant.schemas import UserCreateTenant, UserResetPassword, UserUpdateTenant

# Roles permitidos para usuarios operativos: JAMAS se permite crear otro admin
# desde este módulo. Unicidad de admin por tenant.
ALLOWED_OPERATIONAL_ROLES = {"analyst", "viewer"}
FORBIDDEN_ADMIN_ROLE = "tenant_admin"


class TenantService:
    """Gestión de recursos del tenant: usuarios operativos de la empresa.

    Reglas de oro:
    - El `client_id` SIEMPRE proviene del admin autenticado (nunca del body).
    - Los roles asignables restringen a 'analyst' y 'viewer'.
    - Un usuario solo puede gestionar usuarios de su PROPIA empresa.

    Separación de capas: el acceso a datos vive en los repositorios
    (`TenantUserRepository`, `ClientRepository`); aquí solo queda lógica
    de negocio, validaciones y control de la transacción (`commit`).

    Inyección: el constructor acepta `Session` por compatibilidad (los
    tests y llamadores previos construyen `TenantService(db)`), pero los
    repositorios pueden inyectarse explícitamente desde los routers vía
    `Depends()` (ver `tenant/router.py`).
    """

    def __init__(
        self,
        db: Session,
        users: TenantUserRepository | None = None,
        clients: ClientRepository | None = None,
        roles: RoleRepository | None = None,
        tokens: VerificationTokenRepository | None = None,
    ):
        self.db = db
        self.users = users or TenantUserRepository(db)
        self.clients = clients or ClientRepository(db)
        self.roles = roles or RoleRepository(db)
        self.tokens = tokens or VerificationTokenRepository(db)

    # ------------------------------------------------------------------
    # Alta de usuarios operativos
    # ------------------------------------------------------------------
    def create_tenant_user(self, admin_client_id: int, data: UserCreateTenant) -> User:
        """Registra un usuario operativo (analyst/viewer) en el tenant del admin."""
        # 1. El rol solicitado debe existir y ser operativo (no admin)
        role = self._get_operational_role(data.role_name)

        # 2. Unicidad global del correo
        existing_user = self.users.find_by_email(data.email)
        if existing_user:
            raise EntityAlreadyExistsError(
                "El correo electrónico ya se encuentra registrado.",
            )

        # 3. El tenant del admin debe existir y estar activo
        client = self.clients.find_active_by_id(admin_client_id)
        if not client:
            raise EntityNotFoundError(
                "La empresa del administrador no existe o está inactiva.",
            )

        # 4. Crear usuario vinculado al tenant del admin, sin verificar
        new_user = User(
            client_id=admin_client_id,
            role_id=role.id,
            email=data.email,
            hashed_password=get_hash_password(data.password),
            is_active=True,
            is_verified=False,
        )
        self.users.add(new_user)  # flush: obtiene new_user.id sin confirmar

        # 5. Token de verificación + aviso, dentro de la misma transacción
        verification_token = self.tokens.create_for_user(new_user.id)
        self.db.commit()
        self.db.refresh(new_user)

        send_verification_email(new_user.email, verification_token)

        return new_user

    # ------------------------------------------------------------------
    # Actualización de estado / rol
    # ------------------------------------------------------------------
    def update_tenant_user(
        self, admin_client_id: int, user_id: int, data: UserUpdateTenant
    ) -> User:
        """Actualiza el rol o el estado de un usuario del PROPIO tenant."""
        user = self._get_tenant_user(admin_client_id, user_id)

        if data.role_name is not None:
            # Se permite cambiar entre roles operativos; nunca crear admins
            role = self._get_operational_role(data.role_name)
            user.role_id = role.id

        if data.is_active is not None:
            # No permitir que el admin se desactive a sí mismo
            if user.is_active and not data.is_active:
                self._guard_not_last_admin_action(admin_client_id, user)
            user.is_active = data.is_active

        self.db.commit()
        self.db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # Reseteo de contraseña (soporte descentralizado: lo resuelve el admin)
    # ------------------------------------------------------------------
    def reset_tenant_user_password(
        self, admin_client_id: int, user_id: int, data: UserResetPassword
    ) -> User:
        """Resetea la contraseña de un usuario del propio tenant."""
        user = self._get_tenant_user(admin_client_id, user_id)
        user.hashed_password = get_hash_password(data.new_password)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # Listado de usuarios del tenant
    # ------------------------------------------------------------------
    def list_tenant_users(self, admin_client_id: int) -> list[User]:
        """Lista todos los usuarios (admin incluido) de la empresa del admin."""
        return self._tenant_users(admin_client_id).list_tenant_entities()

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _tenant_users(self, admin_client_id: int) -> TenantUserRepository:
        """Vista del repositorio de usuarios acotada al tenant del admin.

        El scope SIEMPRE proviene del `client_id` del JWT del admin
        autenticado (nunca del body del request).
        """
        return self.users.for_tenant(admin_client_id)

    def _get_operational_role(self, role_name: str) -> Role:
        """Valida que el rol exista y NO sea administrativo.

        El lookup name→Role pasa por `RoleRepository`, cuyo cache en
        memoria a nivel de proceso evita repetir la consulta; la
        recuperación del objeto por PK aprovecha el identity-map de la
        sesión (sin query si ya está cargada).
        """
        if role_name == FORBIDDEN_ADMIN_ROLE:
            raise ForbiddenActionError(
                "Solo puede existir un administrador por empresa.",
            )
        if role_name not in ALLOWED_OPERATIONAL_ROLES:
            raise InvalidRequestError(
                "Rol no permitido para usuarios operativos. "
                f"Roles válidos: {', '.join(sorted(ALLOWED_OPERATIONAL_ROLES))}.",
            )

        role = self.roles.find_by_name_cached(role_name)
        if role is None:  # inexistente, o la DB cambió bajo los pies del cache
            raise EntityNotFoundError(f"El rol '{role_name}' no existe en el sistema.")
        return role

    def _get_tenant_user(self, admin_client_id: int, user_id: int) -> User:
        """Obtiene un usuario verificando que pertenezca al tenant del admin."""
        user = self._tenant_users(admin_client_id).get_tenant_entity(user_id)
        if not user:
            raise EntityNotFoundError(
                "El usuario no existe o no pertenece a tu empresa.",
            )
        return user

    def _guard_not_last_admin_action(self, admin_client_id: int, user: User) -> None:
        """Evita auto-desactivarse: el admin usa rutas exclusivas de admin."""
        if user.role.name == FORBIDDEN_ADMIN_ROLE:
            raise ForbiddenActionError(
                "El administrador no puede modificarse a sí mismo desde este endpoint.",
            )
