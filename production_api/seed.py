"""Genera los datos simulados de produccion a partir de los pedidos del ERP.

Solo se usa para preparar la simulacion: lee el ERP una vez y escribe un JSON.
La API de produccion carga ese JSON y no vuelve a tocar el ERP.

Reglas:
- Pedido ya enviado en el ERP  -> completado (con retraso si salio tarde).
- Pedido sin enviar            -> pendiente, en_produccion, bloqueado o retrasado.

El reparto es determinista: los mismos pedidos generan siempre los mismos
estados, asi las respuestas del sistema se pueden comprobar a mano.

Uso:
    uv run python -m production_api.seed
"""

import json
import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from production_api.models import ProductionOrder, ProductionStatus

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

NORTHWIND_DB_PATH = Path(os.getenv("NORTHWIND_DB_PATH", "data/northwind.db"))
PRODUCTION_DATA_PATH = Path(os.getenv("PRODUCTION_DATA_PATH", "data/production_orders.json"))

# (order_id, fecha de pedido, fecha requerida, fecha de envio o None)
ErpOrder = tuple[int, date, date, date | None]

LINES = ["Linea 1", "Linea 2", "Linea 3"]
BLOCK_REASONS = [
    "Falta de materia prima: proveedor sin stock",
    "Incidencia de calidad: lote retenido para inspeccion",
    "Averia en la maquina de envasado",
    "Pendiente de aprobacion del cliente sobre las especificaciones",
    "Pedido retenido por riesgo de credito del cliente",
]
DELAY_REASONS = [
    "Retraso en la entrega de materia prima",
    "Saturacion de la linea de produccion",
    "Mantenimiento no planificado",
    "Reproceso por defecto de calidad",
]
# Los pedidos abiertos se reparten entre estos estados por turnos.
OPEN_STATUS_CYCLE = [
    ProductionStatus.IN_PRODUCTION,
    ProductionStatus.BLOCKED,
    ProductionStatus.DELAYED,
    ProductionStatus.PENDING,
]


def resolve(path: Path) -> Path:
    """Convierte una ruta relativa en absoluta respecto a la raiz del proyecto."""
    return path if path.is_absolute() else BASE_DIR / path


def _to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def read_erp_orders(db_path: Path) -> list[ErpOrder]:
    """Lee del ERP los cuatro datos de cada pedido que necesita la simulacion."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT OrderID, date(OrderDate), date(RequiredDate), date(ShippedDate) "
            "FROM Orders ORDER BY OrderID"
        ).fetchall()
    finally:
        con.close()
    return [(oid, _to_date(o), _to_date(r), _to_date(s)) for oid, o, r, s in rows]


def _completed(order_id: int, ordered: date, due: date, shipped: date, rng: random.Random) -> ProductionOrder:
    delay_days = max(0, (shipped - due).days)
    return ProductionOrder(
        order_id=order_id,
        status=ProductionStatus.COMPLETED,
        progress_pct=100,
        production_line=rng.choice(LINES),
        due_date=due,
        started_at=min(ordered + timedelta(days=1), shipped),
        estimated_completion=shipped,
        completed_at=shipped,
        delay_days=delay_days,
        delay_reason=rng.choice(DELAY_REASONS) if delay_days else None,
        updated_at=shipped,
    )


def _open(
    order_id: int, ordered: date, due: date, status: ProductionStatus, today: date, rng: random.Random
) -> ProductionOrder:
    tomorrow = today + timedelta(days=1)
    started = min(ordered + timedelta(days=1), today)
    order = ProductionOrder(
        order_id=order_id,
        status=status,
        progress_pct=0,
        production_line=rng.choice(LINES),
        due_date=due,
        updated_at=today,
    )

    if status is ProductionStatus.PENDING:
        order.estimated_completion = max(tomorrow, due - timedelta(days=rng.randint(1, 3)))
    elif status is ProductionStatus.IN_PRODUCTION:
        order.started_at = started
        order.progress_pct = rng.randint(10, 90)
        order.estimated_completion = max(tomorrow, due - timedelta(days=rng.randint(1, 5)))
    elif status is ProductionStatus.DELAYED:
        order.started_at = started
        order.progress_pct = rng.randint(20, 80)
        order.delay_days = rng.randint(2, 12)
        order.delay_reason = rng.choice(DELAY_REASONS)
        order.estimated_completion = due + timedelta(days=order.delay_days)
    elif status is ProductionStatus.BLOCKED:
        order.started_at = started
        order.progress_pct = rng.randint(0, 60)
        order.block_reason = rng.choice(BLOCK_REASONS)
        order.blocked_since = max(started, today - timedelta(days=rng.randint(1, 5)))
        # Sin fecha prevista: no se sabe cuando termina hasta que se desbloquee.
    return order


def generate_orders(erp_orders: list[ErpOrder], today: date | None = None) -> list[ProductionOrder]:
    """Convierte los pedidos del ERP en pedidos de produccion simulados."""
    today = today or date.today()
    orders: list[ProductionOrder] = []
    open_count = 0

    for order_id, ordered, due, shipped in erp_orders:
        # Un generador aleatorio por pedido, con el id como semilla: los datos
        # de un pedido son siempre los mismos y no dependen de los demas.
        rng = random.Random(order_id)

        if shipped is not None:
            orders.append(_completed(order_id, ordered, due, shipped, rng))
            continue

        if due <= today + timedelta(days=1):
            # Vence hoy o manana y sigue abierto: ya no puede llegar a tiempo.
            status = ProductionStatus.DELAYED
        else:
            status = OPEN_STATUS_CYCLE[open_count % len(OPEN_STATUS_CYCLE)]
            open_count += 1
        orders.append(_open(order_id, ordered, due, status, today, rng))

    return orders


def write_orders(orders: list[ProductionOrder], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [order.model_dump(mode="json") for order in orders]
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    source = resolve(NORTHWIND_DB_PATH)
    target = resolve(PRODUCTION_DATA_PATH)
    if not source.exists():
        raise SystemExit(f"No existe {source}. Ejecuta antes: uv run python scripts/prepare_northwind.py")

    generated = generate_orders(read_erp_orders(source))
    write_orders(generated, target)

    print(f"{len(generated)} pedidos de produccion escritos en {target}")
    for status in ProductionStatus:
        print(f"  {status.value}: {sum(o.status is status for o in generated)}")
