"""Construye la base de datos del ERP (Northwind) con las fechas actualizadas.

Northwind es de 1996-1998. Para que preguntas como "pedidos de este mes"
tengan respuesta, se desplazan todas las fechas de los pedidos el mismo
numero de dias, de forma que el ultimo pedido caiga en el dia de hoy.
Las distancias entre fechas (plazos, retrasos) no cambian.

La base se reconstruye siempre desde data/northwind_source.sql, asi que el
script se puede ejecutar las veces que haga falta y el resultado es el mismo.

Uso:
    uv run python scripts/prepare_northwind.py

Origen de los datos: https://github.com/jpwhite3/northwind-SQLite3 (licencia MIT).
"""

import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

# Permite ejecutar el script directamente: anade la raiz del proyecto a los imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, get_settings  # noqa: E402

SOURCE_SQL = BASE_DIR / "data" / "northwind_source.sql"
DATE_COLUMNS = ("OrderDate", "RequiredDate", "ShippedDate")


def build_database(db_path: Path, today: date | None = None, source_sql: Path = SOURCE_SQL) -> int:
    """Crea la base en db_path y devuelve los dias que se han desplazado las fechas."""
    today = today or date.today()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Se construye en un archivo temporal y se renombra al final: si algo
    # falla a medias, la base anterior sigue intacta.
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    tmp_path.unlink(missing_ok=True)

    con = sqlite3.connect(tmp_path)
    try:
        con.executescript(source_sql.read_text(encoding="utf-8"))

        (last_order,) = con.execute("SELECT date(max(OrderDate)) FROM Orders").fetchone()
        shift_days = (today - date.fromisoformat(last_order)).days

        # date(valor, '+N days') suma dias y deja la fecha como 'AAAA-MM-DD'.
        # Si el valor es NULL (pedido sin enviar) el resultado sigue siendo NULL.
        assignments = ", ".join(f"{col} = date({col}, :shift)" for col in DATE_COLUMNS)
        con.execute(f"UPDATE Orders SET {assignments}", {"shift": f"{shift_days:+d} days"})
        con.commit()
    finally:
        con.close()

    os.replace(tmp_path, db_path)
    return shift_days


def print_summary(db_path: Path) -> None:
    """Muestra una comprobacion rapida de la base generada."""
    con = sqlite3.connect(db_path)
    try:
        total, first, last, open_orders = con.execute(
            "SELECT count(*), min(OrderDate), max(OrderDate), sum(ShippedDate IS NULL) FROM Orders"
        ).fetchone()
        month_orders, month_amount = con.execute(
            """
            SELECT count(DISTINCT o.OrderID),
                   round(sum(d.UnitPrice * d.Quantity * (1 - d.Discount)), 2)
            FROM Orders o
            JOIN "Order Details" d ON d.OrderID = o.OrderID
            WHERE strftime('%Y-%m', o.OrderDate) = strftime('%Y-%m', 'now', 'localtime')
            """
        ).fetchone()
    finally:
        con.close()

    print(f"Pedidos: {total} (del {first} al {last})")
    print(f"Pedidos sin enviar: {open_orders}")
    print(f"Pedidos de este mes: {month_orders}, importe {month_amount}")


if __name__ == "__main__":
    settings = get_settings()
    target = settings.resolve(settings.northwind_db_path)
    shift = build_database(target)
    print(f"Base creada en {target} (fechas desplazadas {shift} dias)")
    print_summary(target)
