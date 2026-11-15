"""Muestra lo que hay guardado en cada fuente de datos, sin modelo de lenguaje.

Uso con Docker:
    docker compose run --rm cli python scripts/inspect_data.py erp
    docker compose run --rm cli python scripts/inspect_data.py sql "SELECT * FROM Customers LIMIT 5"
    docker compose run --rm cli python scripts/inspect_data.py production
    docker compose run --rm cli python scripts/inspect_data.py chroma
    docker compose run --rm cli python scripts/inspect_data.py search "penalización por retraso"

erp         tablas del ERP, cuantas filas tiene cada una y unos pedidos de ejemplo
sql         ejecuta una consulta de solo lectura contra el ERP
production  estados de fabricacion y los pedidos abiertos
chroma      cada fragmento indexado: documento, pagina, texto y el inicio de su vector
search      la busqueda vectorial tal cual la recibe el agente de documentos
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402


def erp_connection() -> sqlite3.Connection:
    settings = get_settings()
    path = settings.resolve(settings.northwind_db_path)
    if not path.exists():
        raise SystemExit(f"No existe {path}. Arranca el proyecto primero (init-data lo crea).")
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)  # solo lectura
    con.row_factory = sqlite3.Row
    return con


def print_rows(rows: list[sqlite3.Row], limit: int = 20) -> None:
    if not rows:
        print("(sin filas)")
        return
    columns = rows[0].keys()
    widths = [max(len(str(c)), *(min(len(str(r[c])), 40) for r in rows[:limit])) for c in columns]
    print("  ".join(str(c).ljust(w) for c, w in zip(columns, widths)))
    print("  ".join("-" * w for w in widths))
    for row in rows[:limit]:
        print("  ".join(str(row[c])[:40].ljust(w) for c, w in zip(columns, widths)))
    if len(rows) > limit:
        print(f"... y {len(rows) - limit} filas mas")


def show_erp() -> None:
    con = erp_connection()
    print("Tablas del ERP (filas):")
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        (count,) = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()
        print(f"  {name:<24} {count:>6}")
    print("\nLas tres que usa la aplicacion: Customers, Orders, \"Order Details\".")
    print("\nPedidos sin enviar (los 'pendientes' del ERP):")
    print_rows(con.execute(
        """SELECT o.OrderID, o.CustomerID, c.CompanyName, o.OrderDate, o.RequiredDate,
                  round(sum(d.UnitPrice * d.Quantity * (1 - d.Discount)), 2) AS Importe
             FROM Orders o JOIN Customers c ON c.CustomerID = o.CustomerID
             JOIN "Order Details" d ON d.OrderID = o.OrderID
            WHERE o.ShippedDate IS NULL GROUP BY o.OrderID ORDER BY o.RequiredDate"""
    ).fetchall(), limit=25)


def run_sql(query: str) -> None:
    try:
        print_rows(erp_connection().execute(query).fetchall(), limit=50)
    except sqlite3.Error as exc:
        raise SystemExit(f"Error de SQL: {exc}")


def show_production() -> None:
    settings = get_settings()
    path = settings.resolve(Path(os.getenv("PRODUCTION_DATA_PATH", "data/production_orders.json")))
    orders = json.loads(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for order in orders:
        counts[order["status"]] = counts.get(order["status"], 0) + 1
    print(f"{len(orders)} pedidos en {path}:")
    for status, count in counts.items():
        print(f"  {status:<14} {count}")
    print("\nPedidos abiertos (no completados):")
    for order in orders:
        if order["status"] != "completado":
            reason = order.get("block_reason") or order.get("delay_reason") or ""
            print(f"  {order['order_id']}  {order['status']:<13} {order['progress_pct']:>3}%  {reason}")


def show_chroma() -> None:
    import chromadb

    from app.rag.store import COLLECTION_NAME

    # Se abre la base con el cliente de Chroma directamente: para leer lo
    # guardado no hace falta cargar el modelo de embeddings.
    settings = get_settings()
    path = settings.resolve(settings.chroma_dir)
    collection = chromadb.PersistentClient(path=str(path)).get_collection(COLLECTION_NAME)
    data = collection.get(include=["documents", "metadatas", "embeddings"])
    print(f"Base vectorial en {path}: {len(data['ids'])} fragmentos en la coleccion '{COLLECTION_NAME}'\n")
    rows = sorted(zip(data["ids"], data["metadatas"], data["documents"], data["embeddings"]),
                  key=lambda r: (r[1]["document"], r[1]["page"], r[1]["chunk"]))
    for chunk_id, meta, text, vector in rows:
        print(f"[{chunk_id}]  {meta['document']}  pag. {meta['page']}  trozo {meta['chunk']}  ({len(text)} caracteres)")
        print(f"   texto:  {' '.join(text.split())[:160]}...")
        print(f"   vector: {len(vector)} numeros -> [{', '.join(f'{v:.3f}' for v in vector[:6])}, ...]\n")


def show_search(query: str) -> None:
    from app.rag.retrieval import search

    settings = get_settings()
    print(f"Busqueda: «{query}»  (top {settings.rag_top_k}, relevancia minima {settings.rag_min_relevance})\n")
    results = search(query)
    if not results:
        print("Ningun fragmento supera la relevancia minima: el agente diria que los documentos no lo recogen.")
    for hit in results:
        print(f"[{hit['relevance']}] {hit['document']} pag. {hit['page']}")
        print(f"   {' '.join(hit['text'].split())}\n")


if __name__ == "__main__":
    command, *rest = sys.argv[1:] or ["help"]
    if command == "erp":
        show_erp()
    elif command == "sql" and rest:
        run_sql(" ".join(rest))
    elif command == "production":
        show_production()
    elif command == "chroma":
        show_chroma()
    elif command == "search" and rest:
        show_search(" ".join(rest))
    else:
        print(__doc__)
