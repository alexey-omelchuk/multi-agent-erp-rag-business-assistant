"""Tools del sistema de produccion: estado de fabricacion de los pedidos."""

from typing import Literal

from langchain_core.tools import tool

from app.data_sources.production import ProductionApiError, get_production_client

MAX_ORDERS = 50

ProductionStatus = Literal["pendiente", "en_produccion", "bloqueado", "retrasado", "completado"]


def _compact(order: dict) -> dict:
    """Quita los campos vacios: menos texto para el modelo, misma informacion."""
    return {key: value for key, value in order.items() if value is not None}


def _error(exc: ProductionApiError) -> dict:
    # Se devuelve el error como dato en lugar de lanzarlo: asi el agente
    # puede explicar que produccion no responde en vez de romperse.
    return {"error": str(exc)}


@tool(parse_docstring=True)
def get_production_status(order_ids: list[int]) -> dict:
    """Consulta en el sistema de produccion el estado de fabricacion de uno o varios pedidos.

    Devuelve de cada pedido su estado (pendiente, en_produccion, bloqueado,
    retrasado o completado), el avance, la fecha prevista de fin y, si aplica,
    el motivo del bloqueo o los dias y el motivo del retraso.
    Produccion no conoce a los clientes: solo trabaja con numeros de pedido.

    Args:
        order_ids: Numeros de pedido, por ejemplo [11039, 11054].
    """
    order_ids = order_ids[:MAX_ORDERS]
    try:
        orders = get_production_client().orders_by_id(order_ids)
    except ProductionApiError as exc:
        return _error(exc)
    result: dict = {"orders": [_compact(order) for order in orders]}
    missing = sorted(set(order_ids) - {order["order_id"] for order in orders})
    if missing:
        result["not_found"] = missing
    return result


@tool(parse_docstring=True)
def list_production_orders(status: ProductionStatus) -> dict:
    """Lista los pedidos que estan en un estado de fabricacion concreto.

    Usala para preguntas como "que pedidos estan bloqueados y por que" o "que
    pedidos van con retraso". Devuelve numeros de pedido, no clientes.

    Args:
        status: Estado a consultar.
    """
    try:
        data = get_production_client().orders_by_status(status, limit=MAX_ORDERS)
    except ProductionApiError as exc:
        return _error(exc)
    result = {"status": status, "total": data["total"], "orders": [_compact(o) for o in data["items"]]}
    if data["total"] > len(data["items"]):
        result["note"] = f"Solo se muestran los {len(data['items'])} primeros de {data['total']} pedidos."
    return result


@tool
def get_production_summary() -> dict:
    """Devuelve cuantos pedidos hay en cada estado de fabricacion (pendiente, en_produccion, bloqueado, retrasado, completado)."""
    try:
        return get_production_client().summary()
    except ProductionApiError as exc:
        return _error(exc)


PRODUCTION_TOOLS = [get_production_status, list_production_orders, get_production_summary]
