"""Esquemas Pydantic del sistema de produccion: lo que entra y sale por la API."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ProductionStatus(str, Enum):
    """Estados posibles de un pedido en fabrica."""

    PENDING = "pendiente"  # aun no ha entrado en fabricacion
    IN_PRODUCTION = "en_produccion"  # fabricandose y dentro de plazo
    BLOCKED = "bloqueado"  # parado por una incidencia (ver block_reason)
    DELAYED = "retrasado"  # fabricandose, pero terminara despues de due_date
    COMPLETED = "completado"  # fabricacion terminada


class ProductionOrder(BaseModel):
    """Estado de fabricacion de un pedido. order_id es el OrderID del ERP."""

    order_id: int
    status: ProductionStatus
    progress_pct: int = Field(ge=0, le=100, description="Avance de la fabricacion, de 0 a 100")
    production_line: str
    due_date: date = Field(description="Fecha comprometida con el cliente")
    started_at: date | None = None
    estimated_completion: date | None = Field(
        default=None, description="Fecha prevista de fin. Vacia si el pedido esta bloqueado"
    )
    completed_at: date | None = None
    delay_days: int = Field(default=0, ge=0, description="Dias de retraso respecto a due_date")
    delay_reason: str | None = None
    block_reason: str | None = None
    blocked_since: date | None = None
    updated_at: date


class ProductionOrderList(BaseModel):
    """Resultado de un listado: total de coincidencias y la pagina devuelta."""

    total: int
    items: list[ProductionOrder]


class ProductionSummary(BaseModel):
    """Numero de pedidos en cada estado."""

    total: int
    by_status: dict[ProductionStatus, int]
