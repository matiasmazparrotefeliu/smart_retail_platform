"""Rutas del módulo catalog: catálogo maestro y enlaces de monitoreo.

Todos los endpoints están protegidos en doble capa:
1. `get_current_user` → exige un JWT válido (identidad autenticada).
2. `RoleChecker([...])` → RBAC por rol:
   - Escritura (alta de productos / enlaces): `tenant_admin`, `analyst`.
   - Lectura: los tres roles (`viewer` incluido, solo lectura).

El `client_id` SIEMPRE proviene del token del usuario autenticado;
nunca del body de la petición (aislamiento multi-tenant).

Patrón Repository: el acceso a datos vive en los repositorios
(`src/modules/catalog/repositories.py`, inyectados vía `Depends()`).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.core.auth_handler import RoleChecker
from src.core.database import get_db
from src.modules.auth.models import User
from src.modules.catalog.repositories import (
    MonitoredURLRepository,
    ProductRepository,
)
from src.modules.catalog.schemas import (
    MonitoredURLCreate,
    MonitoredURLResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
)
from src.modules.catalog.service import CatalogService

_readers = RoleChecker(["tenant_admin", "analyst", "viewer"])
_writers = RoleChecker(["tenant_admin", "analyst"])


def get_product_repository(db: Session = Depends(get_db)) -> ProductRepository:
    """Inyecta el repositorio de productos ligado a la sesión del request."""
    return ProductRepository(db)


def get_monitored_url_repository(db: Session = Depends(get_db)) -> MonitoredURLRepository:
    """Inyecta el repositorio de enlaces ligado a la sesión del request."""
    return MonitoredURLRepository(db)


class CatalogRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/catalog", tags=["Catálogo Maestro"])

        # Registro de rutas usando add_api_route en el constructor
        self.router.add_api_route(
            path="/products",
            endpoint=self.create_product,
            methods=["POST"],
            response_model=ProductResponse,
            status_code=status.HTTP_201_CREATED,
            summary="El tenant da de alta un producto en su catálogo maestro.",
        )

        self.router.add_api_route(
            path="/products",
            endpoint=self.list_products,
            methods=["GET"],
            response_model=ProductListResponse,
            summary="Listado paginado del catálogo propio, con filtros opcionales.",
        )

        self.router.add_api_route(
            path="/urls",
            endpoint=self.create_url,
            methods=["POST"],
            response_model=MonitoredURLResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Asocia un enlace de retailer a un producto del propio tenant.",
        )

        self.router.add_api_route(
            path="/urls/{product_id}",
            endpoint=self.list_product_urls,
            methods=["GET"],
            response_model=list[MonitoredURLResponse],
            summary="Lista los retailers y enlaces vinculados a un producto del tenant.",
        )

    def create_product(
        self,
        data: ProductCreate,
        db: Session = Depends(get_db),
        products: ProductRepository = Depends(get_product_repository),
        user: User = Depends(_writers),
    ):
        """Alta de producto; el `client_id` se inyecta desde el JWT."""
        service = CatalogService(db, products=products)
        return service.create_product(client_id=user.client_id, data=data)

    def list_products(
        self,
        db: Session = Depends(get_db),
        products: ProductRepository = Depends(get_product_repository),
        user: User = Depends(_readers),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        brand: Optional[str] = Query(default=None),
        main_category: Optional[str] = Query(default=None),
        is_active: Optional[bool] = Query(default=None),
    ):
        """Listado paginado filtrado estrictamente por el tenant del usuario."""
        service = CatalogService(db, products=products)
        items, total = service.list_products(
            client_id=user.client_id,
            page=page,
            page_size=page_size,
            brand=brand,
            main_category=main_category,
            is_active=is_active,
        )
        return ProductListResponse(items=items, total=total, page=page, page_size=page_size)

    def create_url(
        self,
        data: MonitoredURLCreate,
        db: Session = Depends(get_db),
        urls: MonitoredURLRepository = Depends(get_monitored_url_repository),
        user: User = Depends(_writers),
    ):
        """Asocia un enlace de competencia a un producto maestro del tenant."""
        service = CatalogService(db, urls=urls)
        return service.create_monitored_url(client_id=user.client_id, data=data)

    def list_product_urls(
        self,
        product_id: int,
        db: Session = Depends(get_db),
        urls: MonitoredURLRepository = Depends(get_monitored_url_repository),
        user: User = Depends(_readers),
    ):
        """Consulta de retailers y enlaces de un producto del propio tenant."""
        service = CatalogService(db, urls=urls)
        return service.list_product_urls(client_id=user.client_id, product_id=product_id)
