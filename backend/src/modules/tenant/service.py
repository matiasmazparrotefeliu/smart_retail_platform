from sqlalchemy.orm import Session

from src.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ForbiddenActionError,
    InvalidRequestError,
)
from src.core.security import (
    create_access_token,
    get_hash_password,
    verify_password,
)
from src.modules.auth.models import Role, User, VerificationToken
from src.modules.auth.role_cache import get_role_id
from src.modules.common.verification import (
    issue_verification_token,
    send_verification_email,
)
from src.modules.tenant.schemas import UserCreateTenant, UserResetPassword, UserUpdateTenant
from src.modules.tenant.models import Client

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
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Alta de usuarios operativos
    # ------------------------------------------------------------------
    def create_tenant_user(self, admin_client_id: int, data: UserCreateTenant) -> User:
        """Registra un usuario operativo (analyst/viewer) en el tenant del admin."""
        # 1. El rol solicitado debe existir y ser operativo (no admin)
        role = self._get_operational_role(data.role_name)

        # 2. Unicidad global del correo
        existing_user = self.db.query(User).filter(User.email == data.email).first()
        if existing_user:
            raise EntityAlreadyExistsError(
                "El correo electrónico ya se encuentra registrado.",
            )

        # 3. El tenant del admin debe existir y estar activo
        client = (
            self.db.query(Client)
            .filter(Client.id == admin_client_id, Client.is_active.is_(True))
            .first()
        )
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
        self.db.add(new_user)
        self.db.flush()  # Obtiene new_user.id sin confirmar la transacción

        # 5. Token de verificación + aviso, dentro de la misma transacción
        verification_token = issue_verification_token(self.db, user_id=new_user.id)
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
        return (
            self.db.query(User)
            .filter(User.client_id == admin_client_id)
            .order_by(User.created_at)
            .all()
        )

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _get_operational_role(self, role_name: str) -> Role:
        """Valida que el rol exista y NO sea administrativo.

        El lookup name→id pasa por el cache en memoria; la recuperación del
        objeto por PK aprovecha el identity-map de la sesión (sin query si
        ya está cargada).
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

        role_id = get_role_id(self.db, role_name)
        if role_id is None:
            raise EntityNotFoundError(f"El rol '{role_name}' no existe en el sistema.")
        role = self.db.get(Role, role_id)
        if role is None:  # por si la DB cambió bajo los pies del cache
            raise EntityNotFoundError(f"El rol '{role_name}' no existe en el sistema.")
        return role

    def _get_tenant_user(self, admin_client_id: int, user_id: int) -> User:
        """Obtiene un usuario verificando que pertenezca al tenant del admin."""
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.client_id == admin_client_id)
            .first()
        )
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