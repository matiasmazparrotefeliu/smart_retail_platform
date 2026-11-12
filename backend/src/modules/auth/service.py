from sqlalchemy.orm import Session

from src.core.datetime_utils import utc_now
from src.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ForbiddenActionError,
    InvalidRequestError,
    UnauthorizedError,
)
from src.core.security import (
    create_access_token,
    get_hash_password,
    verify_password,
)
from src.modules.auth.models import User
from src.modules.auth.repositories import (
    RoleRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.modules.tenant.repositories import ClientRepository as TenantClientRepository
from src.modules.tenant.models import Client
from src.modules.auth.schemas import UserLogin, UserRegister
from src.modules.common.verification import send_verification_email

# Nombre del rol administrativo garantizado en el onboarding de una empresa.
ADMIN_ROLE_NAME = "tenant_admin"
ADMIN_ROLE_DESCRIPTION = "Administrador de la empresa"


class AuthService:
    """Onboarding y autenticación de la plataforma.

    Separación de capas: el acceso a datos vive en los repositorios
    (`UserRepository`, `RoleRepository`, `VerificationTokenRepository` y
    `ClientRepository`); aquí solo queda lógica de negocio, validaciones
    y control de la transacción (`commit`).

    Inyección: el constructor acepta `Session` por compatibilidad (los
    tests y llamadores previos construyen `AuthService(db)`), pero los
    repositorios pueden inyectarse explícitamente desde los routers vía
    `Depends()` (ver `auth/router.py`).
    """

    def __init__(
        self,
        db: Session,
        users: UserRepository | None = None,
        clients: TenantClientRepository | None = None,
        roles: RoleRepository | None = None,
        tokens: VerificationTokenRepository | None = None,
    ):
        self.db = db
        self.users = users or UserRepository(db)
        self.clients = clients or TenantClientRepository(db)
        self.roles = roles or RoleRepository(db)
        self.tokens = tokens or VerificationTokenRepository(db)

    def register_company_and_admin(self, data: UserRegister) -> User:
        """Registra un nuevo cliente (tenant), asigna el rol de administrador y crea el usuario."""
        # 1. Verificar si el correo ya existe
        existing_user = self.users.find_by_email(data.email)
        if existing_user:
            raise EntityAlreadyExistsError(
                "El correo electrónico ya se encuentra registrado.",
            )

        # 2. Buscar o crear por defecto el rol 'tenant_admin'
        # (cache en memoria del repo: consulta la DB solo la primera vez por proceso)
        admin_role = self.roles.get_or_create(
            ADMIN_ROLE_NAME, ADMIN_ROLE_DESCRIPTION
        )

        # 3. Crear la empresa (Client)
        new_client = self.clients.add(
            Client(name=data.company_name, is_active=True)
        )

        # 4. Crear el usuario administrador (inactivo hasta verificar el correo)
        hashed_pwd = get_hash_password(data.password)
        new_user = self.users.add(
            User(
                client_id=new_client.id,
                role_id=admin_role.id,
                email=data.email,
                hashed_password=hashed_pwd,
                is_active=True,
                is_verified=False,
            )
        )  # flush: obtiene new_user.id sin confirmar

        # 5. Token de verificación + "correo" (stub DEV), misma transacción
        verification_token = self.tokens.create_for_user(new_user.id)
        self.db.commit()  # Único commit: client + role + user + token de forma atómica
        self.db.refresh(new_user)

        send_verification_email(data.email, verification_token)

        return new_user

    def verify_account(self, token: str) -> User:
        """Valida el token de verificación y activa la cuenta del usuario."""
        # 1. Validar que el token exista y no haya expirado
        record = self.tokens.find_by_token(token)
        if not record or record.expires_at < utc_now():
            raise InvalidRequestError("Token de verificación inválido o expirado.")

        # 2. Localizar al usuario asociado
        user = self.users.get_by_id(record.user_id)
        if not user:
            raise EntityNotFoundError("Usuario no encontrado para el token indicado.")

        # 3. Activar la cuenta y consumir el token (un solo uso)
        if not user.is_verified:
            user.is_verified = True
            self.tokens.delete(record)
            self.db.commit()
            self.db.refresh(user)

        return user

    def authenticate_user(self, data: UserLogin) -> str:
        """Valida las credenciales del usuario y retorna un token JWT de acceso."""
        user = self.users.find_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError(
                "Credenciales incorrectas o correo no registrado.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_verified:
            raise ForbiddenActionError("Cuenta no verificada")

        if not user.is_active:
            raise ForbiddenActionError("La cuenta se encuentra desactivada.")

        token_data = {
            "sub": str(user.id),
            "client_id": user.client_id,
            "role": user.role.name,
        }
        access_token = create_access_token(data=token_data)
        return access_token
