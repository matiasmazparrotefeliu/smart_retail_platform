import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.modules.auth.router import AuthRouter
from src.modules.tenant.router import TenantRouter
from src.core.config import settings
from src.core.exceptions import DomainError

app = FastAPI()

app.include_router(AuthRouter().router, prefix=settings.api_v1_prefix)
app.include_router(TenantRouter().router, prefix=settings.api_v1_prefix)


@app.exception_handler(DomainError)
async def domain_exception_handler(request, exc: DomainError):
  """Traduce excepciones de dominio a respuestas HTTP.

  Los servicios lanzan dominio (404/409/403/401/...); aquí se decide UNA
  sola vez cómo convertirse en respuesta HTTP (status + contenido JSON).
  """
  return JSONResponse(
      status_code=exc.status_code,
      content={"detail": exc.detail},
      headers=exc.headers,
  )

@app.get("/")
def read_root():
    print("----------------------------")
    return {"Hello": "World"}

@app.get("/health")
def health_check():
    return {"status": "ok"}