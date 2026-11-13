"""POST /api/query: pregunta en lenguaje natural -> respuesta, fuentes y razonamiento."""

import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.model import ModelNotConfiguredError
from app.api.schemas import QueryRequest, QueryResponse
from app.services.query_service import QueryService, get_query_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["query"])


def query_service_dependency() -> QueryService:
    # El servicio (y con el, el modelo) se crea en la primera peticion. Si el
    # modelo no esta configurado, se responde 503 con un mensaje claro.
    try:
        return get_query_service()
    except ModelNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


# Endpoint "def" (no "async def"): la consulta tarda segundos y es bloqueante.
# FastAPI la ejecuta en un hilo aparte y el servidor sigue atendiendo a otros.
@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, service: Annotated[QueryService, Depends(query_service_dependency)]):
    """Responde una pregunta de negocio con el sistema multi-agente."""
    try:
        result = service.ask(request.question, request.session_id)
    except Exception as exc:
        # Fallo del modelo (clave incorrecta, limite de uso, caida del proveedor...).
        logger.exception("query_failed session=%s", request.session_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"El modelo de lenguaje no ha podido responder: {type(exc).__name__}: {exc}",
        ) from exc
    return asdict(result)
