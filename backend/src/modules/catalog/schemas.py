from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    """Esquema para el alta de un producto en el catálogo maestro del tenant.

    El `client_id` NO viaja en el request: lo inyecta el service desde
    el token JWT del usuario autenticado (aislamiento multi-tenant).
    """
    sku: str
    name: str
    brand: str
    main_category: str
    sub_category: Optional[str] = None


class ProductResponse(BaseModel):
    """Respuesta de un producto del catálogo maestro."""
    id: int
    client_id: int
    sku: str
    name: str
    brand: str
    main_category: str
    sub_category: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    """Respuesta paginada del listado del catálogo."""
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class MonitoredURLCreate(BaseModel):
    """Esquema para asociar un enlace de retailer a un producto del catálogo."""
    product_id: int
    retailer_name: str
    url: str


class MonitoredURLResponse(BaseModel):
    """Respuesta de un enlace de retailer vinculado a un producto maestro."""
    id: int
    product_id: int
    retailer_name: str
    url: str
    is_active: bool
    last_scraped_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
