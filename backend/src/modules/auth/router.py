from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.auth import schemas
from src.modules.auth.service import AuthService
from src.modules.auth.schemas import Token, UserResponse, UserRegister, UserLogin, VerifyAccount

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

    def register(self, data: UserRegister, db: Session = Depends(get_db)):
        service = AuthService(db)
        return service.register_company_and_admin(data)

    def login(self, data: UserLogin, db: Session = Depends(get_db)):
        service = AuthService(db)
        token = service.authenticate_user(data)
        return {"access_token": token, "token_type": "bearer"}

    def verify_account(self, data: VerifyAccount, db: Session = Depends(get_db)):
        """Activa la cuenta validando el token enviado por correo."""
        service = AuthService(db)
        return service.verify_account(data.token)