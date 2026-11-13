"""Tests del RAG: ingesta, busqueda y tools de documentos.

No se usa el modelo de embeddings real (pesa 220 MB y habria que descargarlo).
Se sustituye por uno falso que cuenta palabras: dos textos se parecen si
comparten palabras. Basta para comprobar toda la mecanica: partir, guardar,
filtrar, citar la pagina y reemplazar documentos.
"""

import hashlib
import math
import re
import unicodedata

import pytest
from langchain_core.embeddings import Embeddings

from app.config import BASE_DIR, get_settings
from app.rag import retrieval
from app.rag.ingest import DocumentError, ingest_pdf, read_pdf_pages, split_pages
from app.rag.store import build_vector_store
from app.tools import documents as document_tools

DOCS_DIR = BASE_DIR / "data" / "docs"
CONTRACT = DOCS_DIR / "contrato_suministro_ernst_handel.pdf"
PROCEDURE = DOCS_DIR / "procedimiento_pedidos_bloqueados.pdf"


class WordCountEmbeddings(Embeddings):
    """Embeddings falsos: cada palabra suma en una posicion fija del vector."""

    DIMENSIONS = 8192

    def _embed(self, text: str) -> list[float]:
        plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
        vector = [0.0] * self.DIMENSIONS
        for word in re.findall(r"[a-z]{4,}", plain):
            position = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIMENSIONS
            vector[position] += 1.0
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture
def store(tmp_path, monkeypatch):
    # Con embeddings de palabras las puntuaciones son mas bajas que con el modelo real.
    monkeypatch.setattr(get_settings(), "rag_min_relevance", 0.05)
    return build_vector_store(tmp_path / "chroma", WordCountEmbeddings())


@pytest.fixture
def indexed_store(store):
    ingest_pdf(CONTRACT, store=store)
    ingest_pdf(PROCEDURE, store=store)
    return store


def test_read_pdf_pages_keeps_page_numbers():
    pages = read_pdf_pages(CONTRACT)
    assert [number for number, _ in pages] == [1, 2]
    assert "Penalizaciones por retraso" in pages[0][1]


def test_file_that_is_not_a_pdf_is_rejected(tmp_path):
    fake = tmp_path / "notas.pdf"
    fake.write_text("esto no es un PDF")
    with pytest.raises(DocumentError):
        read_pdf_pages(fake)


def test_split_respects_chunk_size_and_keeps_metadata():
    chunks = split_pages("contrato.pdf", read_pdf_pages(CONTRACT))
    assert len(chunks) > 2
    assert all(len(chunk.page_content) <= get_settings().rag_chunk_size for chunk in chunks)
    assert {chunk.metadata["document"] for chunk in chunks} == {"contrato.pdf"}
    assert {chunk.metadata["page"] for chunk in chunks} == {1, 2}


def test_ingest_reports_pages_and_chunks(store):
    result = ingest_pdf(CONTRACT, store=store)
    assert result.document == CONTRACT.name
    assert result.pages == 2
    assert result.chunks > 2


def test_ingesting_twice_replaces_instead_of_duplicating(store):
    first = ingest_pdf(CONTRACT, store=store)
    ingest_pdf(CONTRACT, store=store)
    (entry,) = retrieval.list_documents(store)
    assert entry["chunks"] == first.chunks


def test_search_finds_the_penalty_clause_with_its_source(indexed_store):
    results = retrieval.search("penalización por cada día natural de retraso en la entrega", store=indexed_store)
    best = results[0]
    assert best["document"] == CONTRACT.name
    assert best["page"] == 1
    assert "1 %" in best["text"]
    assert 0 < best["relevance"] <= 1
    relevances = [result["relevance"] for result in results]
    assert relevances == sorted(relevances, reverse=True)


def test_search_can_be_limited_to_one_document(indexed_store):
    results = retrieval.search("pedido bloqueado por falta de materia prima", document=PROCEDURE.name, store=indexed_store)
    assert results
    assert {result["document"] for result in results} == {PROCEDURE.name}
    assert any("Compras" in result["text"] for result in results)


def test_search_discards_unrelated_chunks(indexed_store):
    assert retrieval.search("zanahorias hidroponicas marcianas", store=indexed_store) == []


def test_search_returns_at_most_top_k(indexed_store):
    results = retrieval.search("pedido cliente proveedor entrega", store=indexed_store)
    assert 0 < len(results) <= get_settings().rag_top_k


def test_list_documents(indexed_store):
    documents = retrieval.list_documents(indexed_store)
    assert [entry["document"] for entry in documents] == [CONTRACT.name, PROCEDURE.name]
    assert documents[0]["pages"] == 2


def test_data_survives_reopening_the_store(tmp_path):
    ingest_pdf(CONTRACT, store=build_vector_store(tmp_path / "chroma", WordCountEmbeddings()))
    reopened = build_vector_store(tmp_path / "chroma", WordCountEmbeddings())
    assert len(retrieval.list_documents(reopened)) == 1


# --- Las tools: la capa que ve el agente ---


@pytest.fixture
def tools(indexed_store, monkeypatch):
    monkeypatch.setattr(retrieval, "get_vector_store", lambda: indexed_store)
    return document_tools


def test_search_tool_returns_citable_results(tools):
    result = tools.search_documents.invoke({"query": "límite de crédito y retención de pedidos"})
    assert result["results"][0]["document"] == CONTRACT.name
    assert set(result["results"][0]) == {"document", "page", "relevance", "text"}


def test_search_tool_says_when_nothing_matches(tools):
    result = tools.search_documents.invoke({"query": "zanahorias hidroponicas marcianas"})
    assert result["results"] == []
    assert "note" in result


def test_list_tool(tools):
    result = tools.list_documents.invoke({})
    assert len(result["documents"]) == 2


def test_list_tool_with_empty_store(store, monkeypatch):
    monkeypatch.setattr(retrieval, "get_vector_store", lambda: store)
    assert document_tools.list_documents.invoke({})["documents"] == []
