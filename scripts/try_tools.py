"""Llama a cada tool a mano, sin ningun modelo de lenguaje.

Sirve para ver exactamente lo que recibira el agente. Necesita la base del
ERP creada y la API de produccion arrancada.

Uso con Docker:
    docker compose run --rm cli python scripts/try_tools.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.erp import ERP_TOOLS, get_customer_orders, get_orders_by_id, get_orders_summary, search_customers  # noqa: E402
from app.tools.production import (  # noqa: E402
    PRODUCTION_TOOLS,
    get_production_status,
    get_production_summary,
    list_production_orders,
)


def show(tool, args: dict) -> dict:
    result = tool.invoke(args)
    print(f"\n>>> {tool.name}({args})")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1500])
    return result


if __name__ == "__main__":
    print("Lo que el modelo ve de cada tool:")
    for tool in ERP_TOOLS + PRODUCTION_TOOLS:
        print(f"- {tool.name}: {tool.description.splitlines()[0]}")
        print(f"    argumentos: {list(tool.args)}")

    # Pregunta 1 del enunciado, hecha a mano: pedidos pendientes de un cliente y su estado.
    show(search_customers, {"query": "Ernst"})
    pending = show(get_customer_orders, {"customer_id": "ERNSH", "only_pending": True})
    show(get_production_status, {"order_ids": [order["order_id"] for order in pending["orders"]]})

    # Pregunta 2: pedidos bloqueados, motivo y a que cliente pertenecen.
    blocked = show(list_production_orders, {"status": "bloqueado"})
    show(get_orders_by_id, {"order_ids": [order["order_id"] for order in blocked["orders"]]})

    # Pregunta 4: resumen del mes.
    show(get_orders_summary, {})
    show(get_production_summary, {})
