"""Tools del ERP: clientes, pedidos e importes."""

from calendar import monthrange
from datetime import date

from langchain_core.tools import tool

from app.data_sources.erp import get_erp_repository

MAX_ORDERS = 50


def _order_list(orders: list[dict]) -> dict:
    """Limita el tamano de la respuesta sin ocultar cuantos pedidos hay."""
    result = {"total": len(orders), "orders": orders[:MAX_ORDERS]}
    if len(orders) > MAX_ORDERS:
        result["note"] = f"Solo se muestran los {MAX_ORDERS} primeros de {len(orders)} pedidos."
    return result


@tool(parse_docstring=True)
def search_customers(query: str) -> dict:
    """Busca clientes en el ERP por nombre de empresa, persona de contacto o codigo.

    Usala primero cuando la pregunta nombre a un cliente: devuelve el customer_id
    que necesitan las demas herramientas del ERP.

    Args:
        query: Texto a buscar, por ejemplo "Ernst" o "ALFKI".
    """
    customers = get_erp_repository().search_customers(query)
    if not customers:
        return {"customers": [], "note": f"Ningun cliente coincide con '{query}'."}
    return {"customers": customers}


@tool(parse_docstring=True)
def list_customers(country: str | None = None) -> dict:
    """Lista todos los clientes con su numero de pedidos, pedidos pendientes e importe total, de mayor a menor importe.

    Usala para preguntas generales sobre los clientes ("que clientes hay",
    "todos los clientes y sus pedidos", "mejores clientes"). Es una sola
    consulta: no llames a get_customer_orders cliente por cliente para esto.

    Args:
        country: Pais para filtrar, en ingles como en el ERP (por ejemplo "Germany", "Spain"). Sin valor, todos.
    """
    customers = get_erp_repository().customers_overview(country)
    if not customers:
        return {"total": 0, "customers": [], "note": f"Ningun cliente con pais '{country}'."}
    return {
        "total": len(customers),
        "total_orders": sum(customer["orders"] for customer in customers),
        "customers": customers,
    }


@tool(parse_docstring=True)
def get_customer_orders(customer_id: str, only_pending: bool = False) -> dict:
    """Devuelve los pedidos de un cliente con sus fechas, importe y estado en el ERP.

    El estado del ERP solo distingue "enviado" y "pendiente" (sin enviar). El
    motivo por el que un pedido sigue pendiente no esta en el ERP, sino en el
    sistema de produccion.

    Args:
        customer_id: Codigo del cliente en el ERP, por ejemplo "ERNSH".
        only_pending: Si es true, devuelve solo los pedidos sin enviar.
    """
    return _order_list(get_erp_repository().customer_orders(customer_id, only_pending))


@tool
def get_pending_orders() -> dict:
    """Devuelve todos los pedidos sin enviar del ERP, de cualquier cliente, con su cliente, fechas e importe."""
    return _order_list(get_erp_repository().pending_orders())


@tool(parse_docstring=True)
def get_orders_by_id(order_ids: list[int]) -> dict:
    """Devuelve el cliente, las fechas y el importe de unos pedidos concretos.

    Usala para saber a que cliente pertenece un pedido del que solo se conoce el
    numero, por ejemplo los pedidos que el sistema de produccion marca como
    bloqueados o retrasados.

    Args:
        order_ids: Numeros de pedido, por ejemplo [11039, 11054].
    """
    orders = get_erp_repository().orders_by_id(order_ids)
    result = _order_list(orders)
    missing = sorted(set(order_ids) - {order["order_id"] for order in orders})
    if missing:
        result["not_found"] = missing
    return result


@tool(parse_docstring=True)
def get_orders_summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Resume los pedidos hechos en un periodo: cuantos, importe total, enviados, pendientes y clientes principales.

    Sin fechas resume el mes actual. Incluye los numeros de los pedidos
    pendientes (pending_order_ids) para poder consultar su estado en produccion.

    Args:
        start_date: Primer dia del periodo, en formato AAAA-MM-DD.
        end_date: Ultimo dia del periodo, en formato AAAA-MM-DD.
    """
    today = date.today()
    try:
        start = date.fromisoformat(start_date) if start_date else today.replace(day=1)
        end = (
            date.fromisoformat(end_date)
            if end_date
            else start.replace(day=monthrange(start.year, start.month)[1])
        )
    except ValueError:
        return {"error": "Las fechas deben tener el formato AAAA-MM-DD."}
    if end < start:
        return {"error": "end_date no puede ser anterior a start_date."}
    return get_erp_repository().orders_summary(start, end)


ERP_TOOLS = [search_customers, list_customers, get_customer_orders, get_pending_orders, get_orders_by_id, get_orders_summary]
