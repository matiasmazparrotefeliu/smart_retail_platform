from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.modules.tenant.models import Client

class Role(Base):
    """Modelo para la gestión de roles y permisos (RBAC)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # Ej: 'tenant_admin', 'analyst', 'viewer'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relación inversa con usuarios
    users: Mapped[list["User"]] = relationship(back_populates="role", cascade="all, delete-orphan")

class User(Base):
    """Modelo para los usuarios del sistema asociados a una empresa y con un rol."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # Controla si validó el correo electrónico
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones ORM
    client: Mapped["Client"] = relationship(back_populates="users")
    role: Mapped["Role"] = relationship(back_populates="users")
    verification_tokens: Mapped[list["VerificationToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class VerificationToken(Base):
    """Token temporal de un solo uso para la verificación del correo electrónico.

    Se genera en el registro (onboarding) y permite activar la cuenta
    cambiando `is_verified` del usuario asociado a True.
    """

    __tablename__ = "verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relación inversa con el usuario
    user: Mapped["User"] = relationship(back_populates="verification_tokens")
