"""Patrón Repository: acceso a datos desacoplado de la lógica de negocio.

El repositorio encapsula TODAS las interacciones con la base de datos
(queries, `add`, `delete`), dejando a los services la lógica de negocio
y el control de la transacción.

Convención CRÍTICA (contrato de la capa):
- Los repositorios JAMÁS hacen `commit()`/`rollback()`: solo `flush()`
  (necesario para obtener la PK de filas nuevas sin confirmar). Quien
  decide cuándo es atómica la transacción es el service; esto permite
  que varios repos participen de UNA misma transacción.
- Los repositorios devuelven `Model | None` y NO lanzan excepciones
  HTTP: interpretar `None` como error de negocio es responsabilidad
  del service (`EntityNotFoundError`, etc.).

Clases:
- `BaseRepository`: CRUD genérico tipado sobre el modelo declarado.
- `TenantScopedRepository`: variante con aislamiento multi-tenant
  forzado por construcción. Se instancia por tenant con
  `Repo.for_tenant(client_id)` y a partir de ahí toda query lleva el
  filtro de `client_id` pegado (Regla de Oro: nunca una consulta sin
  aislar por tenant).
"""

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """CRUD genérico sobre un modelo ORM.

    Cada subclase declara `model` con su modelo SQLAlchemy concreto:

        class ClientRepository(BaseRepository[Client]):
            model = Client
    """

    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, entity_id: int) -> ModelT | None:
        """Recupera una entidad por su PK (usa identity-map de la sesión)."""
        return self.db.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        """Agrega la entidad a la sesión y hace flush (asigna la PK).

        NO confirma: la transacción la controla el llamador.
        """
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Marca la entidad para eliminación (efectiva al confirmar)."""
        self.db.delete(entity)


class TenantScopedRepository(BaseRepository[ModelT]):
    """Repositorio de entidades que pertenecen a un tenant (`client_id`).

    Regla de Oro del sistema: ninguna consulta sin filtrar por tenant.
    Este repositorio lo garantiza POR CONSTRUCCIÓN: el scope se fija
    con `for_tenant(client_id)` (el `client_id` SIEMPRE proviene del
    token JWT del usuario autenticado, nunca del request) y todos los
    métodos de lectura van pre-filtrados.
    """

    # Nombre de la columna FK hacia `clients` en el modelo concreto.
    client_id_field: str = "client_id"

    # Campo usado para ordenar listados por defecto.
    order_by_field: str = "created_at"

    client_id: int

    def for_tenant(self, client_id: int) -> "TenantScopedRepository[ModelT]":
        """Devuelve una vista del repositorio acotada a un tenant.

        Crea una instancia ligera ligada a la MISMA sesión, evitando
        que una misma instancia cambie de tenant a mitad de un caso de
        uso (el `client_id` del scope es inmutable una vez fijado).
        """
        scoped = type(self)(self.db)
        scoped.client_id = client_id
        return scoped

    def _scoped_query(self):
        """Query del modelo filtrada por el tenant del scope."""
        return self.db.query(self.model).filter(
            getattr(self.model, self.client_id_field) == self.client_id
        )

    def get_tenant_entity(self, entity_id: int) -> ModelT | None:
        """Recupera por PK dentro del tenant.

        `None` significa "no existe O no pertenece al tenant"; el
        service decide el mensaje y el código HTTP sin revelar cuál
        de las dos causas fue.
        """
        return self._scoped_query().filter(self.model.id == entity_id).first()

    def list_tenant_entities(self) -> list[ModelT]:
        """Lista todas las entidades del tenant, ordenadas por defecto."""
        return (
            self._scoped_query()
            .order_by(getattr(self.model, self.order_by_field))
            .all()
        )
