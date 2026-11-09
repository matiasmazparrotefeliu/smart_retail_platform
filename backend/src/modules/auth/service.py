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
from src.modules.auth.models import Role, User, VerificationToken
from src.modules.auth.role_cache import get_role_id, set_role_id
from src.modules.auth.schemas import UserLogin, UserRegister
from src.modules.common.verification import (
    issue_verification_token,
    send_verification_email,
)
from src.modules.tenant.models import Client


class AuthService:

  def __init__(self, db: Session):
    self.db = db

  def register_company_and_admin(self, data: UserRegister) -> User:
    """Registra un nuevo cliente (tenant), asigna el rol de administrador y crea el usuario."""
    # 1. Verificar si el correo ya existe
    existing_user = self.db.query(User).filter(User.email == data.email).first()
    if existing_user:
      raise EntityAlreadyExistsError(
          "El correo electrónico ya se encuentra registrado.",
      )

    # 2. Buscar o crear por defecto el rol 'tenant_admin'
    # (cache en memoria: consulta la DB solo la primera vez por proceso)
    admin_role_id = get_role_id(self.db, "tenant_admin")
    if admin_role_id is None:
      admin_role = Role(
          name="tenant_admin", description="Administrador de la empresa"
      )
      self.db.add(admin_role)
      self.db.flush()
      admin_role_id = admin_role.id
      set_role_id("tenant_admin", admin_role_id)

    # 3. Crear la empresa (Client)
    new_client = Client(name=data.company_name, is_active=True)
    self.db.add(new_client)
    self.db.flush()

    # 4. Crear el usuario administrador (inactivo hasta verificar el correo)
    hashed_pwd = get_hash_password(data.password)
    new_user = User(
        client_id=new_client.id,
        role_id=admin_role_id,
        email=data.email,
        hashed_password=hashed_pwd,
        is_active=True,
        is_verified=False,
    )
    self.db.add(new_user)
    self.db.flush()  # Obtiene new_user.id sin confirmar la transacción

    # 5. Token de verificación + "correo" (stub DEV), misma transacción
    verification_token = issue_verification_token(self.db, user_id=new_user.id)
    self.db.commit()  # Único commit: client + role + user + token de forma atómica
    self.db.refresh(new_user)

    send_verification_email(data.email, verification_token)

    return new_user

  def verify_account(self, token: str) -> User:
    """Valida el token de verificación y activa la cuenta del usuario."""
    # 1. Validar que el token exista y no haya expirado
    record = (
        self.db.query(VerificationToken)
        .filter(VerificationToken.token == token)
        .first()
    )
    if not record or record.expires_at < utc_now():
      raise InvalidRequestError("Token de verificación inválido o expirado.")

    # 2. Localizar al usuario asociado
    user = self.db.query(User).filter(User.id == record.user_id).first()
    if not user:
      raise EntityNotFoundError("Usuario no encontrado para el token indicado.")

    # 3. Activar la cuenta y consumir el token (un solo uso)
    if not user.is_verified:
      user.is_verified = True
      self.db.delete(record)
      self.db.commit()
      self.db.refresh(user)

    return user

  def authenticate_user(self, data: UserLogin) -> str:
    """Valida las credenciales del usuario y retorna un token JWT de acceso."""
    user = self.db.query(User).filter(User.email == data.email).first()
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