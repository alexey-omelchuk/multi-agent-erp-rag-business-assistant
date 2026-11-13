"""Base vectorial (Chroma): guarda cada trozo de texto junto a su vector."""

from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.config import get_settings
from app.rag.embeddings import get_embeddings

COLLECTION_NAME = "documents"


def build_vector_store(persist_dir: Path, embeddings: Embeddings) -> Chroma:
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
        # Distancia coseno: compara la direccion de los vectores, que es lo
        # que representa el significado, y da una relevancia entre 0 y 1.
        collection_configuration={"hnsw": {"space": "cosine"}},
    )


@lru_cache
def get_vector_store() -> Chroma:
    settings = get_settings()
    return build_vector_store(settings.resolve(settings.chroma_dir), get_embeddings())
