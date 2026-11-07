import os
from fastapi import FastAPI

from src.modules.auth.router import AuthRouter
from src.core.config import settings

app = FastAPI()

app.include_router(AuthRouter().router, prefix=settings.api_v1_prefix)

@app.get("/")
def read_root():
    print("----------------------------")
    return {"Hello": "World"}

@app.get("/health")
def health_check():
    return {"status": "ok"}