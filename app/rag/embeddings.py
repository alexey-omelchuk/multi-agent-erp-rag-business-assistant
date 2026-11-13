"""Modelo de embeddings: convierte un texto en un vector de numeros.

Dos textos que hablan de lo mismo dan vectores cercanos, aunque no compartan
palabras. Se usa un modelo local (fastembed, sin GPU): no necesita clave de
API, no tiene coste y el contenido de los documentos no sale de la maquina.
"""

from functools import lru_cache

from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from app.config import get_settings


class LocalEmbeddings(Embeddings):
    """Adapta fastembed a la interfaz de embeddings de LangChain."""

    def __init__(self, model_name: str):
        # La primera vez descarga el modelo; despues lo lee de la cache local.
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embeddings() -> Embeddings:
    return LocalEmbeddings(get_settings().embedding_model)


if __name__ == "__main__":
    # Descarga el modelo. Se usa al construir la imagen de Docker para que el
    # contenedor no dependa de internet al arrancar.
    vector = get_embeddings().embed_query("prueba")
    print(f"Modelo {get_settings().embedding_model} listo ({len(vector)} dimensiones)")
