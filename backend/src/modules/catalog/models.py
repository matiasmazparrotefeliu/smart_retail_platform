from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.datetime_utils import utc_now


class Product(Base):
    """Catálogo maestro del tenant: identidad canónica del producto.

    El producto vive de forma independiente a los enlaces web de los
    retailers (`monitored_urls`): un mismo producto maestro puede
    compararse contra múltiples fuentes.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("client_id", "sku", name="uq_products_client_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)  # Código interno de referencia
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    main_category: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Enlaces de retailers/competencia asociados a este producto maestro
    urls: Mapped[list["MonitoredURL"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class MonitoredURL(Base):
    """Enlace de e-commerce de un retailer (competencia) a monitorear.

    Ejemplo: un producto maestro del tenant asociado a su ficha en
    Frávega, Cetrogar o MercadoLibre. `last_scraped_at` es la marca de
    control temporal que utilizará el futuro motor de scraping.
    """

    __tablename__ = "monitored_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    retailer_name: Mapped[str] = mapped_column(String(50), nullable=False)  # Ej: 'fravega'
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relación inversa con el producto maestro
    product: Mapped["Product"] = relationship(back_populates="urls")
