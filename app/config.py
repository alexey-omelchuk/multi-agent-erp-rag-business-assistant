"""Configuracion de la aplicacion.

Todos los valores que cambian entre entornos (tu PC, Docker, produccion)
se leen de variables de entorno. El resto del codigo nunca lee el entorno
directamente: pide los ajustes con get_settings().
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz del proyecto: la carpeta que contiene a "app/".
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga ".env" en las variables de entorno del proceso. Asi tambien lo ven
# las librerias de los proveedores, que buscan OPENAI_API_KEY por su cuenta.
# Si una variable ya existe en el entorno (caso de Docker), no la pisa.
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    """Ajustes de la aplicacion, validados al arrancar."""

    model_config = SettingsConfigDict(extra="ignore")

    # Modelo de lenguaje, en formato "proveedor:modelo".
    model: str = "openai:gpt-5.6-luna"
    # Vacio: se usa el valor por defecto del proveedor. Los modelos de
    # razonamiento no suelen admitir una temperatura fija.
    model_temperature: float | None = None

    # Azure OpenAI (solo si MODEL empieza por "azure_openai:").
    azure_openai_api_key: SecretStr | None = None
    azure_openai_base_url: str | None = None
    azure_openai_api_version: str | None = None
    azure_openai_model_deployment_name: str | None = None

    # Langfuse (opcional): si hay claves, cada consulta se envia como traza.
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "http://localhost:3000"

    # Fuentes de datos.
    northwind_db_path: Path = Path("data/northwind.db")
    production_api_url: str = "http://localhost:8001"
    chroma_dir: Path = Path("chroma")

    # RAG.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_chunk_size: int = Field(default=500, ge=100)  # caracteres por trozo
    rag_chunk_overlap: int = Field(default=80, ge=0)  # caracteres repetidos entre trozos seguidos
    rag_top_k: int = Field(default=5, ge=1)  # trozos que devuelve una busqueda
    rag_min_relevance: float = Field(default=0.4, ge=0, le=1)

    # Limites de una consulta: llamadas a tools que puede hacer cada agente.
    # Evitan que una pregunta demasiado amplia se quede en un bucle de minutos.
    agent_max_tool_calls: int = Field(default=10, ge=1)  # cada subagente, por encargo
    coordinator_max_tool_calls: int = Field(default=8, ge=1)  # el coordinador: plan y delegaciones

    # Comportamiento.
    memory_max_interactions: int = Field(default=5, ge=1)
    log_level: str = "INFO"

    def resolve(self, path: Path) -> Path:
        """Convierte una ruta relativa en absoluta respecto a la raiz del proyecto."""
        return path if path.is_absolute() else BASE_DIR / path


@lru_cache
def get_settings() -> Settings:
    """Devuelve los ajustes. Se crean una sola vez y se reutilizan."""
    return Settings()


if __name__ == "__main__":
    # Comprobacion rapida: uv run python -m app.config
    for name, value in get_settings().model_dump().items():
        print(f"{name} = {value}")
