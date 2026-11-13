"""Tests de la API principal.

Como en el Project 4 del curso de FastAPI: se sustituye la dependencia real
(el servicio con el modelo de lenguaje) por una de prueba. Aqui la de prueba
es el servicio real con un modelo de guion, asi que se recorre todo el camino:
HTTP -> validacion -> agentes -> tools -> traza -> JSON de respuesta.
"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agents.model import ModelNotConfiguredError
from app.api.main import app
from app.api.routers import query as query_router
from app.api.routers.query import query_service_dependency
from app.rag import ingest, retrieval
from tests.test_agents import ERNST_SCRIPT, make_service, sources  # noqa: F401  (fixture)
from tests.test_rag import CONTRACT, store  # noqa: F401  (fixture)
from ui.formatting import format_answer, format_error, format_reasoning


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_script(script):
    service, model = make_service(script)
    app.dependency_overrides[query_service_dependency] = lambda: service
    return model


# --- POST /api/query ---


def test_query_returns_the_format_of_the_specification(client, sources):  # noqa: F811
    use_script(ERNST_SCRIPT)
    response = client.post("/api/query", json={"question": "¿Qué pedidos pendientes tiene Ernst Handel?"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "sources", "reasoning", "session_id", "steps", "duration_ms"}
    assert body["answer"].startswith("Ernst Handel tiene 2 pedidos pendientes")
    assert body["sources"] == ["ERP", "Producción"]
    assert body["reasoning"][-1].startswith("Coordinador: combina los resultados de ERP y Producción")
    assert body["steps"][2] == {
        "agent": "erp-agent", "tool": "search_customers", "source": "ERP",
        "args": {"query": "Ernst Handel"}, "ok": True, "duration_ms": body["steps"][2]["duration_ms"],
    }
    assert body["session_id"]


def test_query_with_session_id_keeps_memory(client, sources):  # noqa: F811
    use_script(ERNST_SCRIPT + [AIMessage(content="El bloqueado es el 11072.")])
    first = client.post("/api/query", json={"question": "¿Qué pedidos pendientes tiene Ernst Handel?", "session_id": "s1"})
    second = client.post("/api/query", json={"question": "¿Y cuáles de esos están bloqueados?", "session_id": "s1"})

    assert first.json()["session_id"] == second.json()["session_id"] == "s1"
    assert second.json()["answer"] == "El bloqueado es el 11072."
    assert second.json()["sources"] == []


@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "a"}, {"question": "x" * 2001}])
def test_query_validates_the_question(client, payload):
    use_script([])
    assert client.post("/api/query", json=payload).status_code == 422


def test_query_without_configured_model_returns_503(client, monkeypatch):
    def fail():
        raise ModelNotConfiguredError("No se ha podido iniciar el modelo 'openai:x'.")

    monkeypatch.setattr(query_router, "get_query_service", fail)
    response = client.post("/api/query", json={"question": "¿Qué pedidos hay?"})
    assert response.status_code == 503
    assert "No se ha podido iniciar el modelo" in response.json()["detail"]


def test_query_when_the_model_fails_returns_502(client):
    use_script([])  # guion vacio: el modelo falso falla en la primera llamada
    response = client.post("/api/query", json={"question": "¿Qué pedidos hay?"})
    assert response.status_code == 502
    assert "El modelo de lenguaje no ha podido responder" in response.json()["detail"]


# --- Documentos ---


@pytest.fixture
def documents(store, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ingest, "get_vector_store", lambda: store)
    monkeypatch.setattr(retrieval, "get_vector_store", lambda: store)
    return store


def test_upload_pdf_indexes_it(client, documents):
    with open(CONTRACT, "rb") as pdf:
        response = client.post("/api/documents", files={"file": ("contrato.pdf", pdf, "application/pdf")})

    assert response.status_code == 201
    assert response.json()["document"] == "contrato.pdf"
    assert response.json()["pages"] == 2
    assert client.get("/api/documents").json()["documents"] == [response.json()]
    assert retrieval.search("penalización por cada día natural de retraso", store=documents)[0]["document"] == "contrato.pdf"


def test_upload_rejects_files_that_are_not_pdf(client, documents):
    by_name = client.post("/api/documents", files={"file": ("notas.txt", b"hola", "text/plain")})
    by_content = client.post("/api/documents", files={"file": ("falso.pdf", b"esto no es un pdf", "application/pdf")})
    assert by_name.status_code == 415
    assert by_content.status_code == 415
    assert client.get("/api/documents").json()["documents"] == []


def test_upload_ignores_folders_in_the_file_name(client, documents):
    with open(CONTRACT, "rb") as pdf:
        response = client.post("/api/documents", files={"file": ("../../etc/contrato.pdf", pdf, "application/pdf")})
    assert response.status_code == 201
    assert response.json()["document"] == "contrato.pdf"


def test_upload_without_file_returns_422(client):
    assert client.post("/api/documents").status_code == 422


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert ":" in body["model"]


# --- Textos de la interfaz ---


def test_ui_formatting():
    response = {"answer": "Hay 5 bloqueados.", "sources": ["ERP", "Producción"], "steps": [{}, {}], "duration_ms": 12340}
    text = format_answer(response)
    assert text.startswith("Hay 5 bloqueados.")
    assert "**Fuentes:** ERP · Producción" in text
    assert "2 llamadas a herramientas · 12.3 s" in text
    assert "ninguna" in format_answer({"answer": "x", "sources": []})
    assert format_reasoning(["uno", "dos"]) == "1. uno\n2. dos"
    error = format_error(503, "No se ha podido iniciar el modelo 'openai:gpt-5.6-luna'.")
    assert error.startswith("**Error 503.**")
    assert "```text\nNo se ha podido iniciar el modelo 'openai:gpt-5.6-luna'.\n```" in error
