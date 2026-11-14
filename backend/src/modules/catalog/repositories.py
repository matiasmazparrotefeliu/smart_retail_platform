"""Repositorios del módulo catalog.

Encapsulan el acceso a datos de `Product` (catálogo maestro) y
`MonitoredURL` (enlaces de retailers), de modo que el service NO
contiene queries: solo reglas de negocio.

Convención (ver `src/core/repository.py`):
- Sin `commit()`/`rollback()` aquí: el service controla la transacción.
- Devuelven `Model | None`; interpretar `None` como error HTTP es del
  service (evita filtrar si un recurso no existe o no es del tenant).

Regla de Oro: `MonitoredURL` no tiene columna `client_id`, así que
TODA consulta sobre enlaces se resuelve vía join con `products`
(filtrando `products.client_id`) para mantener el aislamiento por
tenant también en esta tabla.
"""

from src.core.repository import BaseRepository, TenantScopedRepository
from src.modules.catalog.models import MonitoredURL, Product


class ProductRepository(TenantScopedRepository[Product]):
    """Productos del catálogo maestro, acotados al tenant del usuario."""

    model = Product
    client_id_field = "client_id"    # default de la base; explícito por legibilidad
    order_by_field = "created_at"    # idem

    def find_by_sku(self, sku: str) -> Product | None:
        """Busca un producto por SKU dentro del tenant del scope."""
        return self._scoped_query().filter(Product.sku == sku).first()

    def list_paginated(
        self,
        page: int,
        page_size: int,
        brand: str | None = None,
        main_category: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Product], int]:
        """Listado paginado con filtros opcionales.

        Devuelve `(items, total)`: `total` cuenta TODAS las filas del
        tenant que cumplen los filtros (sin paginar), para que el
        caller arme la respuesta paginada.
        """
        query = self._scoped_query()
        if brand is not None:
            query = query.filter(Product.brand == brand)
        if main_category is not None:
            query = query.filter(Product.main_category == main_category)
        if is_active is not None:
            query = query.filter(Product.is_active.is_(is_active))

        total = query.count()
        items = (
            query.order_by(Product.created_at, Product.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class MonitoredURLRepository(BaseRepository[MonitoredURL]):
    """Enlaces de retailers, SIEMPRE aislados por tenant vía `products`."""

    model = MonitoredURL

    def list_by_product(self, product_id: int, client_id: int) -> list[MonitoredURL]:
        """Enlaces vinculados a un producto del tenant dado.

        El join con `products` garantiza que solo se devuelvan URLs
        cuyo producto maestro pertenezca al tenant.
        """
        return (
            self.db.query(MonitoredURL)
            .join(MonitoredURL.product)
            .filter(
                Product.client_id == client_id,
                MonitoredURL.product_id == product_id,
            )
            .order_by(MonitoredURL.id)
            .all()
        )
