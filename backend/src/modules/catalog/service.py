from sqlalchemy.orm import Session

from src.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from src.modules.catalog.models import MonitoredURL, Product
from src.modules.catalog.repositories import MonitoredURLRepository, ProductRepository
from src.modules.catalog.schemas import MonitoredURLCreate, ProductCreate


class CatalogService:
    """Gestión del catálogo maestro y de los enlaces de monitoreo.

    Reglas de oro:
    - El `client_id` SIEMPRE proviene del usuario autenticado (JWT);
      nunca del body del request (aislamiento multi-tenant).
    - La identidad canónica (`Product`) es independiente de los
      enlaces web de retailers (`MonitoredURL`).

    Separación de capas: el acceso a datos vive en los repositorios
    (`ProductRepository`, `MonitoredURLRepository`); aquí solo queda
    lógica de negocio, validaciones y control de la transacción
    (`commit`).
    """

    def __init__(
        self,
        db: Session,
        products: ProductRepository | None = None,
        urls: MonitoredURLRepository | None = None,
    ):
        self.db = db
        self.products = products or ProductRepository(db)
        self.urls = urls or MonitoredURLRepository(db)

    # ------------------------------------------------------------------
    # Catálogo maestro: productos
    # ------------------------------------------------------------------
    def create_product(self, client_id: int, data: ProductCreate) -> Product:
        """Da de alta un producto en el catálogo maestro del tenant."""
        products = self.products.for_tenant(client_id)

        existing = products.find_by_sku(data.sku)
        if existing:
            raise EntityAlreadyExistsError(
                "Ya existe un producto con ese SKU en tu catálogo.",
            )

        new_product = Product(
            client_id=client_id,
            sku=data.sku,
            name=data.name,
            brand=data.brand,
            main_category=data.main_category,
            sub_category=data.sub_category,
        )
        products.add(new_product)  # flush: obtiene new_product.id sin confirmar
        self.db.commit()
        self.db.refresh(new_product)
        return new_product

    def list_products(
        self,
        client_id: int,
        page: int,
        page_size: int,
        brand: str | None = None,
        main_category: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Product], int]:
        """Listado paginado del catálogo propio, con filtros opcionales."""
        return self.products.for_tenant(client_id).list_paginated(
            page=page,
            page_size=page_size,
            brand=brand,
            main_category=main_category,
            is_active=is_active,
        )

    # ------------------------------------------------------------------
    # Enlaces de monitoreo (retailers / competencia)
    # ------------------------------------------------------------------
    def create_monitored_url(
        self, client_id: int, data: MonitoredURLCreate
    ) -> MonitoredURL:
        """Asocia un enlace de retailer a un producto del PROPIO tenant."""
        # El producto ancla debe existir dentro del tenant del usuario
        product = self._get_tenant_product(client_id, data.product_id)

        new_url = MonitoredURL(
            product_id=product.id,
            retailer_name=data.retailer_name,
            url=data.url,
        )
        self.urls.add(new_url)  # flush: obtiene new_url.id sin confirmar
        self.db.commit()
        self.db.refresh(new_url)
        return new_url

    def list_product_urls(
        self, client_id: int, product_id: int
    ) -> list[MonitoredURL]:
        """Enlaces de retailers vinculados a un producto del PROPIO tenant."""
        self._get_tenant_product(client_id, product_id)
        return self.urls.list_by_product(product_id, client_id)

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _get_tenant_product(self, client_id: int, product_id: int) -> Product:
        """Obtiene un producto verificando que pertenezca al tenant del usuario."""
        product = self.products.for_tenant(client_id).get_tenant_entity(product_id)
        if not product:
            raise EntityNotFoundError(
                "El producto no existe o no pertenece a tu empresa.",
            )
        return product
