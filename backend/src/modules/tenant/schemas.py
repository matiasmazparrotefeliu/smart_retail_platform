from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional

class UserCreateTenant(BaseModel):
    """Esquema para el alta de un usuario operativo por parte del administrador."""
    email: EmailStr
    password: str
    role_name: str  # Debe ser 'analyst' o 'viewer'

class UserUpdateTenant(BaseModel):
    """Esquema para la actualización de estado o rol de un usuario operativo."""
    is_active: Optional[bool] = None
    role_name: Optional[str] = None

class UserResetPassword(BaseModel):
    """Esquema para el reseteo de contraseña forzado por el administrador."""
    new_password: str

class UserTenantResponse(BaseModel):
    """Respuesta simplificada de la gestión de usuarios del tenant."""
    id: int
    email: str
    role_name: str
    is_active: bool
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)
