"""Tools de documentos: busqueda en los PDF indexados (RAG)."""

from langchain_core.tools import tool

from app.rag import retrieval


@tool(parse_docstring=True)
def search_documents(query: str, document: str | None = None) -> dict:
    """Busca en los documentos PDF indexados (contratos, politicas, procedimientos) los fragmentos mas relacionados con una consulta.

    Usala para preguntas sobre clausulas, condiciones, penalizaciones, plazos o
    procedimientos. Busca por significado, asi que la consulta debe describir el
    tema ("penalizacion por retraso en la entrega"), no ser una sola palabra.
    Cada fragmento indica el documento y la pagina: citalos en la respuesta. Si
    no devuelve fragmentos, la informacion no esta en los documentos.

    Args:
        query: Tema o pregunta a buscar, en lenguaje natural.
        document: Nombre exacto de un documento para buscar solo en el. Sin valor, busca en todos.
    """
    results = retrieval.search(query, document)
    if not results:
        return {"results": [], "note": "Ningun fragmento de los documentos indexados trata sobre esa consulta."}
    return {"results": results}


@tool
def list_documents() -> dict:
    """Devuelve la lista de documentos PDF indexados, con su nombre exacto y su numero de paginas."""
    documents = retrieval.list_documents()
    if not documents:
        return {"documents": [], "note": "Todavia no se ha indexado ningun documento."}
    return {"documents": documents}


DOCUMENT_TOOLS = [search_documents, list_documents]
