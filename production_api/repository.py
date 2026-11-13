"""Acceso a los datos de produccion.

Los endpoints no saben donde viven los datos: piden un ProductionRepository.
Hoy es un JSON cargado en memoria; si manana fuese una base de datos, solo
cambiaria esta clase.
"""

import json
from collections import Counter
from pathlib import Path

from production_api.models import ProductionOrder, ProductionStatus


class ProductionRepository:
    def __init__(self, orders: list[ProductionOrder]):
        self._orders = {order.order_id: order for order in orders}

    @classmethod
    def from_file(cls, path: Path) -> "ProductionRepository":
        if not path.exists():
            raise RuntimeError(
                f"No existe {path}. Genera los datos con: uv run python -m production_api.seed"
            )
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([ProductionOrder.model_validate(item) for item in raw])

    def get(self, order_id: int) -> ProductionOrder | None:
        return self._orders.get(order_id)

    def search(
        self,
        status: ProductionStatus | None = None,
        order_ids: list[int] | None = None,
    ) -> list[ProductionOrder]:
        """Pedidos que cumplen todos los filtros indicados, ordenados por order_id."""
        orders = sorted(self._orders.values(), key=lambda order: order.order_id)
        if status is not None:
            orders = [order for order in orders if order.status is status]
        if order_ids is not None:
            wanted = set(order_ids)
            orders = [order for order in orders if order.order_id in wanted]
        return orders

    def count_by_status(self) -> dict[ProductionStatus, int]:
        counts = Counter(order.status for order in self._orders.values())
        return {status: counts.get(status, 0) for status in ProductionStatus}

    def __len__(self) -> int:
        return len(self._orders)
