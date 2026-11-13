"""Busqueda: de una pregunta a los trozos de documento mas parecidos."""

from langchain_chroma import Chroma

from app.config import get_settings
from app.rag.store import get_vector_store


def search(query: str, document: str | None = None, store: Chroma | None = None) -> list[dict]:
    """Devuelve los trozos mas relevantes para la consulta, del mas al menos parecido.

    Cada resultado lleva el documento y la pagina de donde sale, para poder
    citar la fuente. Los trozos por debajo de la relevancia minima se descartan:
    es preferible no devolver nada a devolver texto que no viene al caso.
    """
    store = store or get_vector_store()
    settings = get_settings()

    results = store.similarity_search_with_relevance_scores(
        query,
        k=settings.rag_top_k,
        filter={"document": document} if document else None,
    )
    return [
        {
            "document": chunk.metadata["document"],
            "page": chunk.metadata["page"],
            "relevance": round(score, 2),
            "text": chunk.page_content,
        }
        for chunk, score in results
        if score >= settings.rag_min_relevance
    ]


def list_documents(store: Chroma | None = None) -> list[dict]:
    """Documentos indexados, con sus paginas y su numero de trozos."""
    store = store or get_vector_store()
    documents: dict[str, dict] = {}
    for metadata in store.get(include=["metadatas"])["metadatas"]:
        entry = documents.setdefault(metadata["document"], {"document": metadata["document"], "pages": 0, "chunks": 0})
        entry["pages"] = max(entry["pages"], metadata["page"])
        entry["chunks"] += 1
    return sorted(documents.values(), key=lambda entry: entry["document"])
