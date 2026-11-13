"""Cliente HTTP del sistema de produccion.

Es la unica parte de la aplicacion que sabe que produccion es una API REST
y que rutas tiene. El resto pide datos con metodos de Python.
"""

from functools import lru_cache

import httpx

from app.config import get_settings


class ProductionApiError(Exception):
    """El sistema de produccion no responde o ha devuelto un error."""


class ProductionClient:
    def __init__(self, base_url: str, http_client: httpx.Client | None = None, timeout: float = 10.0):
        # http_client se puede inyectar: los tests pasan uno conectado a la
        # API en memoria, sin abrir ningun puerto.
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout)

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            response = self._http.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProductionApiError(
                f"El sistema de produccion ha devuelto un error {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProductionApiError("No se ha podido conectar con el sistema de produccion") from exc
        return response.json()

    def orders_by_id(self, order_ids: list[int]) -> list[dict]:
        """Estado de unos pedidos concretos. Los que no existan no aparecen."""
        if not order_ids:
            return []
        data = self._get("/production/orders", {"order_id": order_ids, "limit": len(order_ids)})
        return data["items"]

    def orders_by_status(self, status: str, limit: int = 50) -> dict:
        """Pedidos en un estado. Devuelve {"total": ..., "items": [...]}."""
        return self._get("/production/orders", {"status": status, "limit": limit})

    def summary(self) -> dict:
        """Numero de pedidos en cada estado."""
        return self._get("/production/summary")


@lru_cache
def get_production_client() -> ProductionClient:
    return ProductionClient(get_settings().production_api_url)
