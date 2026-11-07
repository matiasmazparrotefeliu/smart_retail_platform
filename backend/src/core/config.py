"""Configuración central de la aplicación.

Carga las variables de entorno desde el archivo `.env` ubicado en la
**raíz del repositorio** (ruta absoluta, independiente del directorio de
ejecución). El resto de los módulos debe importar SIEMPRE `settings` desde
aquí y nunca leer `os.environ` directamente.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py → parents[3] = raíz del repositorio
PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    """Settings tipados leídos desde `<raíz>/.env` y variables de entorno."""
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    app_name: str = Field(default="Smart Retail API", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    api_v1_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list, alias="CORS_ORIGINS")
    database_url: str = Field(default="postgresql+psycopg://retail:retail@localhost:5432/retail", alias="DATABASE_URL")
    test_database_url: str = Field(default="postgresql+psycopg://retail:retail@localhost:5432/retail_test", alias="TEST_DATABASE_URL")
    secret_key:str = Field(default="super-secret-key-123", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Permite definir CORS_ORIGINS como lista separada por comas."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de Settings."""
    return Settings()

settings = get_settings()