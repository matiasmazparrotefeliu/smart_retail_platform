"""Excepciones de dominio: desacoplan la lógica de negocio de HTTP/FastAPI.

Los servicios NO lanzan `HTTPException` (eso es un detalle de transporte):
lanzan excepciones de dominio que el manejador global de `main.py`
traduce a respuestas HTTP correctas (status code + mensaje).

Beneficios:
- Servicios puros de Python: reutilizables desde consola, workers, etc.
- Un único punto de decisión del mapeo dominio → código HTTP.
- Tests unitarios vía `pytest.raises(DomainError)` sin mockear HTTP.

Jerarquía:
    DomainError (base)
    ├── EntityNotFoundError      → 404
    ├── EntityAlreadyExistsError → 409
    ├── ForbiddenActionError     → 403
    ├── UnauthorizedError        → 401
    └── InvalidRequestError      → 400
"""

from typing import Any


class DomainError(Exception):
    """Base de todas las excepciones de dominio del sistema."""

    #: Código HTTP por defecto; cada subclase lo redefine.
    default_status_code = 400

    def __init__(self, detail: str, *, status_code: int | None = None, headers: dict[str, Any] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code if status_code is not None else self.default_status_code
        # headers opcional (ej. WWW-Authenticate en errores 401)
        self.headers = headers


class EntityNotFoundError(DomainError):
    """Recurso solicitado que no existe (o es invisible por aislamiento)."""

    default_status_code = 404


class EntityAlreadyExistsError(DomainError):
    """Recurso que viola una restricción de unicidad (emails, nombre...)."""

    default_status_code = 409


class ForbiddenActionError(DomainError):
    """La acción existe pero el actor/rol no está autorizado."""

    default_status_code = 403


class UnauthorizedError(DomainError):
    """Credenciales ausentes, inválidas o token corrupto."""

    default_status_code = 401


class InvalidRequestError(DomainError):
    """Los datos o parámetros de la petición no son válidos."""

    default_status_code = 400
