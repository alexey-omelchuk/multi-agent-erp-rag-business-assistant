"""Consultas al ERP (Northwind, SQLite).

Todas las consultas estan escritas aqui y reciben sus valores como parametros
("?" o ":nombre"). El modelo de lenguaje nunca escribe SQL: solo elige una de
estas funciones y le pasa argumentos. Ademas, la base se abre en solo lectura.
"""

import sqlite3
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

# Importe de un pedido: suma de sus lineas con el descuento aplicado.
_ORDER_SELECT = """
    SELECT o.OrderID      AS order_id,
           o.CustomerID   AS customer_id,
           c.CompanyName  AS customer_name,
           o.OrderDate    AS order_date,
           o.RequiredDate AS required_date,
           o.ShippedDate  AS shipped_date,
           (SELECT round(sum(d.UnitPrice * d.Quantity * (1 - d.Discount)), 2)
              FROM "Order Details" d
             WHERE d.OrderID = o.OrderID) AS amount
      FROM Orders o
      LEFT JOIN Customers c ON c.CustomerID = o.CustomerID
"""


def _order(row: sqlite3.Row) -> dict:
    order = dict(row)
    # Para el ERP un pedido esta pendiente mientras no tenga fecha de envio.
    order["erp_status"] = "enviado" if order["shipped_date"] else "pendiente"
    return order


class ErpRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _query(self, sql: str, params: dict | tuple = ()) -> list[sqlite3.Row]:
        if not self._db_path.exists():
            raise FileNotFoundError(
                f"No existe {self._db_path}. Ejecuta: uv run python scripts/prepare_northwind.py"
            )
        # mode=ro: conexion de solo lectura. Aunque hubiese un error en el
        # codigo, desde aqui no se puede modificar el ERP.
        con = sqlite3.connect(f"{self._db_path.as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()

    def search_customers(self, text: str, limit: int = 10) -> list[dict]:
        """Clientes cuyo nombre, contacto o codigo contiene el texto."""
        rows = self._query(
            """
            SELECT CustomerID AS customer_id, CompanyName AS company_name,
                   ContactName AS contact_name, City AS city, Country AS country
              FROM Customers
             WHERE CompanyName LIKE :pattern
                OR ContactName LIKE :pattern
                OR CustomerID = upper(:text)
             ORDER BY CompanyName
             LIMIT :limit
            """,
            {"pattern": f"%{text.strip()}%", "text": text.strip(), "limit": limit},
        )
        return [dict(row) for row in rows]

    def customer_orders(self, customer_id: str, only_pending: bool = False) -> list[dict]:
        """Pedidos de un cliente, del mas reciente al mas antiguo."""
        sql = _ORDER_SELECT + " WHERE o.CustomerID = upper(:customer_id)"
        if only_pending:
            sql += " AND o.ShippedDate IS NULL"
        sql += " ORDER BY o.OrderDate DESC, o.OrderID DESC"
        return [_order(row) for row in self._query(sql, {"customer_id": customer_id.strip()})]

    def pending_orders(self) -> list[dict]:
        """Todos los pedidos sin enviar, ordenados por fecha requerida."""
        sql = _ORDER_SELECT + " WHERE o.ShippedDate IS NULL ORDER BY o.RequiredDate, o.OrderID"
        return [_order(row) for row in self._query(sql)]

    def orders_by_id(self, order_ids: list[int]) -> list[dict]:
        """Datos de unos pedidos concretos (cliente, fechas e importe)."""
        if not order_ids:
            return []
        placeholders = ", ".join("?" for _ in order_ids)
        sql = _ORDER_SELECT + f" WHERE o.OrderID IN ({placeholders}) ORDER BY o.OrderID"
        return [_order(row) for row in self._query(sql, tuple(order_ids))]

    def orders_summary(self, start: date, end: date, top: int = 5) -> dict:
        """Resumen de los pedidos hechos entre dos fechas, ambas incluidas."""
        params = {"start": start.isoformat(), "end": end.isoformat(), "top": top}
        where = " WHERE o.OrderDate BETWEEN :start AND :end"
        orders = [_order(row) for row in self._query(_ORDER_SELECT + where, params)]

        top_customers = self._query(
            """
            SELECT customer_id, customer_name, count(*) AS orders, round(sum(amount), 2) AS amount
              FROM (""" + _ORDER_SELECT + where + """)
             GROUP BY customer_id
             ORDER BY amount DESC
             LIMIT :top
            """,
            params,
        )
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_orders": len(orders),
            "total_amount": round(sum(order["amount"] or 0 for order in orders), 2),
            "shipped_orders": sum(order["erp_status"] == "enviado" for order in orders),
            "pending_orders": sum(order["erp_status"] == "pendiente" for order in orders),
            # Con estos numeros se puede preguntar a produccion en que estado esta cada uno.
            "pending_order_ids": sorted(order["order_id"] for order in orders if order["erp_status"] == "pendiente"),
            "top_customers": [dict(row) for row in top_customers],
        }


@lru_cache
def get_erp_repository() -> ErpRepository:
    settings = get_settings()
    return ErpRepository(settings.resolve(settings.northwind_db_path))
