"""API REST del sistema de produccion simulado.

Arranque:
    uv run uvicorn production_api.main:app --port 8001 --reload

Documentacion interactiva: http://localhost:8001/docs
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request, status

from production_api.models import (
    ProductionOrder,
    ProductionOrderList,
    ProductionStatus,
    ProductionSummary,
)
from production_api.repository import ProductionRepository
from production_api.seed import PRODUCTION_DATA_PATH, resolve


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta una vez al arrancar: carga los datos en memoria.
    app.state.repository = ProductionRepository.from_file(resolve(PRODUCTION_DATA_PATH))
    yield


def get_repository(request: Request) -> ProductionRepository:
    return request.app.state.repository


repository_dependency = Annotated[ProductionRepository, Depends(get_repository)]

router = APIRouter(prefix="/production", tags=["production"])


@router.get("/orders", response_model=ProductionOrderList)
async def list_orders(
    repository: repository_dependency,
    status_filter: Annotated[
        ProductionStatus | None, Query(alias="status", description="Filtra por estado")
    ] = None,
    order_id: Annotated[
        list[int] | None,
        Query(description="Filtra por pedidos concretos. Se puede repetir: ?order_id=1&order_id=2"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Lista pedidos de produccion, con filtros opcionales y paginacion."""
    matches = repository.search(status=status_filter, order_ids=order_id)
    return ProductionOrderList(total=len(matches), items=matches[offset : offset + limit])


@router.get("/orders/{order_id}", response_model=ProductionOrder)
async def get_order(repository: repository_dependency, order_id: Annotated[int, Path(gt=0)]):
    """Estado de fabricacion de un pedido."""
    order = repository.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El pedido {order_id} no existe en produccion",
        )
    return order


@router.get("/summary", response_model=ProductionSummary)
async def get_summary(repository: repository_dependency):
    """Numero de pedidos en cada estado."""
    return ProductionSummary(total=len(repository), by_status=repository.count_by_status())


app = FastAPI(title="Sistema de produccion (simulado)", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
