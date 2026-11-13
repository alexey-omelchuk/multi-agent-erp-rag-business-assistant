"""Ingesta: de un PDF a trozos indexados en la base vectorial.

Uso:
    python -m app.rag.ingest data/docs/contrato.pdf [otro.pdf ...]
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.config import get_settings
from app.rag.store import get_vector_store


class DocumentError(ValueError):
    """El archivo no se puede indexar (no es un PDF valido o no tiene texto)."""


@dataclass
class IngestResult:
    document: str
    pages: int
    chunks: int


def read_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Devuelve (numero de pagina, texto) de cada pagina que tiene texto."""
    try:
        reader = PdfReader(pdf_path)
        pages = [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, start=1)]
    except (PyPdfError, OSError, ValueError) as exc:
        raise DocumentError(f"No se ha podido leer '{pdf_path.name}' como PDF.") from exc

    pages = [(number, text.strip()) for number, text in pages if text.strip()]
    if not pages:
        raise DocumentError(
            f"'{pdf_path.name}' no contiene texto. Si es un documento escaneado, necesita OCR antes de indexarlo."
        )
    return pages


def split_pages(document: str, pages: list[tuple[int, str]]) -> list[Document]:
    """Parte cada pagina en trozos. Cada trozo recuerda su documento y su pagina."""
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    chunks: list[Document] = []
    for page_number, text in pages:
        for index, chunk in enumerate(splitter.split_text(text)):
            chunks.append(
                Document(
                    page_content=chunk,
                    metadata={"document": document, "page": page_number, "chunk": index},
                )
            )
    return chunks


def ingest_pdf(pdf_path: Path, document_name: str | None = None, store: Chroma | None = None) -> IngestResult:
    """Indexa un PDF. Si ya habia un documento con ese nombre, lo sustituye."""
    store = store or get_vector_store()
    document = document_name or pdf_path.name

    pages = read_pdf_pages(pdf_path)
    chunks = split_pages(document, pages)

    # Volver a subir un documento lo reemplaza en lugar de duplicarlo.
    store.delete(where={"document": document})
    ids = [f"{document}:p{chunk.metadata['page']}:c{chunk.metadata['chunk']}" for chunk in chunks]
    store.add_documents(chunks, ids=ids)

    return IngestResult(document=document, pages=len(pages), chunks=len(chunks))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python -m app.rag.ingest archivo.pdf [otro.pdf ...]")
    for argument in sys.argv[1:]:
        result = ingest_pdf(Path(argument))
        print(f"{result.document}: {result.pages} paginas, {result.chunks} trozos indexados")
