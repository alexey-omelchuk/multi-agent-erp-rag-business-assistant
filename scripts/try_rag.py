"""Indexa los PDF de data/docs/ y lanza varias busquedas, sin modelo de lenguaje.

Sirve para ver que devuelve exactamente la busqueda: es lo que recibira el
agente como contexto para redactar su respuesta.

Uso con Docker:
    docker compose run --rm cli python scripts/try_rag.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR  # noqa: E402
from app.rag.ingest import ingest_pdf  # noqa: E402
from app.tools.documents import list_documents, search_documents  # noqa: E402

QUERIES = [
    ("¿Qué penalización hay si un pedido se entrega tarde?", None),
    ("¿Cuándo puede el proveedor retener un pedido por impago?", None),
    ("¿Quién se encarga de un pedido bloqueado por falta de material?", "procedimiento_pedidos_bloqueados.pdf"),
    ("¿Cuál es la política de vacaciones de los empleados?", None),
]

if __name__ == "__main__":
    print("1) Ingesta")
    for pdf_path in sorted((BASE_DIR / "data" / "docs").glob("*.pdf")):
        result = ingest_pdf(pdf_path)
        print(f"   {result.document}: {result.pages} paginas -> {result.chunks} trozos")

    print("\n2) Documentos indexados")
    for entry in list_documents.invoke({})["documents"]:
        print(f"   {entry}")

    print("\n3) Busquedas")
    for query, document in QUERIES:
        scope = f" (solo en {document})" if document else ""
        print(f"\n>>> {query}{scope}")
        response = search_documents.invoke({"query": query, "document": document})
        if not response["results"]:
            print(f"   {response['note']}")
        for hit in response["results"]:
            text = " ".join(hit["text"].split())
            print(f"   [{hit['relevance']}] {hit['document']}, pag. {hit['page']}: {text[:170]}...")
