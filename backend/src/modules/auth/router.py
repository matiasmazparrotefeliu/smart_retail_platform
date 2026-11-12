"""Rutas del módulo auth: onboarding de empresas y autenticación.

Nota transitoria (patrón Repository): el acceso a datos vive en los
repositorios (`src/modules/auth/repositories.py`, inyectados vía
`Depends()`). Los endpoints aún pasan `db` al service porque los tests
existen construyendo `AuthService(db)`; cuando se actualicen, la sesión
dejará de viajar al service por la firma.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth.repositories import (
    RoleRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.modules.tenant.repositories import ClientRepository
from src.modules.auth.service import AuthService
from src.modules.auth.schemas import Token, UserResponse, UserRegister, UserLogin, VerifyAccount


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Inyecta el repositorio de usuarios ligado a la sesión del request."""
    return UserRepository(db)


def get_client_repository(db: Session = Depends(get_db)) -> ClientRepository:
    """Inyecta el repositorio de empresas ligado a la sesión del request.

    Duplicación CONSCIENTE del proveedor de `tenant/router.py` (misma
    clase, mismo contrato): no se importa del otro router porque los
    routers no deben depender entre sí. Si diverge, `ClientRepository`
    es la única fuente de la lógica de datos.
    """
    return ClientRepository(db)


def get_role_repository(db: Session = Depends(get_db)) -> RoleRepository:
    """Inyecta el repositorio de roles (lookup cacheado) del request."""
    return RoleRepository(db)


def get_token_repository(
    db: Session = Depends(get_db),
) -> VerificationTokenRepository:
    """Inyecta el repositorio de tokens de verificación del request."""
    return VerificationTokenRepository(db)


class AuthRouter:
    def __init__(self):
        self.router = APIRouter(prefix="/auth", tags=["Autenticación"])

        # Registro de rutas usando add_api_route y los métodos de la clase
        self.router.add_api_route(
            path="/register",
            endpoint=self.register,
            methods=["POST"],
            response_model=UserResponse,
            status_code=status.HTTP_201_CREATED,
        )

        self.router.add_api_route(
            path="/login",
            endpoint=self.login,
            methods=["POST"],
            response_model=Token,
        )

        self.router.add_api_route(
            path="/verify",
            endpoint=self.verify_account,
            methods=["POST"],
            response_model=UserResponse,
            summary="Activa la cuenta validando el token enviado por correo.",
        )

    def register(
        self,
        data: UserRegister,
        db: Session = Depends(get_db),
        users: UserRepository = Depends(get_user_repository),
        clients: ClientRepository = Depends(get_client_repository),
        roles: RoleRepository = Depends(get_role_repository),
        tokens: VerificationTokenRepository = Depends(get_token_repository),
    ):
        service = AuthService(db, users=users, clients=clients, roles=roles, tokens=tokens)
        return service.register_company_and_admin(data)

    def login(
        self,
        data: UserLogin,
        db: Session = Depends(get_db),
        users: UserRepository = Depends(get_user_repository),
    ):
        service = AuthService(db, users=users)
        token = service.authenticate_user(data)
        return {"access_token": token, "token_type": "bearer"}

    def verify_account(
        self,
        data: VerifyAccount,
        db: Session = Depends(get_db),
        users: UserRepository = Depends(get_user_repository),
        tokens: VerificationTokenRepository = Depends(get_token_repository),
    ):
        """Activa la cuenta validando el token enviado por correo."""
        service = AuthService(db, users=users, tokens=tokens)
        return service.verify_account(data.token)
