"""API principal.

Arranque:
    uvicorn app.api.main:app --port 8000

Documentacion interactiva: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import documents, query
from app.config import get_settings
from app.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="Asistente de negocio multi-agente",
    description="Responde preguntas en lenguaje natural combinando ERP, producción y documentos.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(query.router)
app.include_router(documents.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "model": get_settings().model}
