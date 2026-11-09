from datetime import datetime
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.datetime_utils import utc_now

class Client(Base):
    """Modelo para representar a cada empresa cliente (Tenant)."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relación con los usuarios pertenecientes a esta empresa
    users: Mapped[list["User"]] = relationship(back_populates="client", cascade="all, delete-orphan")