"""Tests del sistema multi-agente, sin modelo de lenguaje real.

El modelo se sustituye por un guion (ScriptedChatModel): asi se decide que
"piensa" cada agente y se comprueba todo lo demas, que es codigo nuestro:
delegacion, ejecucion real de las tools, traza, fuentes, razonamiento y memoria.
Las tools si son las reales: consultan el ERP de prueba y la API de produccion.
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.coordinator import build_coordinator
from app.agents.memory import keep_recent_turns
from app.agents.subagents import build_subagents
from app.data_sources.production import ProductionClient
from app.services.query_service import QueryService
from app.services.trace import SOURCE_BY_TOOL, TraceStep, build_reasoning, build_sources
from app.tools import erp as erp_tools
from app.tools import production as production_tools
from production_api.main import app as production_app
from production_api.main import get_repository
from production_api.models import ProductionOrder
from production_api.repository import ProductionRepository
from tests.conftest import TODAY
from tests.fakes import ScriptedChatModel, tool_call

# Los dos pedidos pendientes de Ernst Handel en el ERP de prueba.
PRODUCTION_ORDERS = [
    ProductionOrder(
        order_id=11008, status="retrasado", progress_pct=30, production_line="Linea 2", due_date=TODAY,
        delay_days=3, delay_reason="Saturacion de la linea", updated_at=TODAY,
    ),
    ProductionOrder(
        order_id=11072, status="bloqueado", progress_pct=10, production_line="Linea 1", due_date=TODAY,
        block_reason="Falta de materia prima", blocked_since=TODAY, updated_at=TODAY,
    ),
]


@pytest.fixture
def sources(erp, monkeypatch):
    """Conecta las tools al ERP de prueba y a la API de produccion en memoria."""
    production_app.dependency_overrides[get_repository] = lambda: ProductionRepository(PRODUCTION_ORDERS)
    client = ProductionClient("http://testserver", http_client=TestClient(production_app))
    monkeypatch.setattr(erp_tools, "get_erp_repository", lambda: erp)
    monkeypatch.setattr(production_tools, "get_production_client", lambda: client)
    yield
    production_app.dependency_overrides.clear()


def make_service(script: list[AIMessage]) -> tuple[QueryService, ScriptedChatModel]:
    model = ScriptedChatModel(script=script)
    return QueryService(build_coordinator(model=model, checkpointer=InMemorySaver())), model


# Guion de la pregunta 1 del enunciado: lo que decidiria cada agente, en orden.
ERNST_SCRIPT = [
    # Coordinador: planifica y delega en el ERP.
    tool_call("write_todos", {"todos": [
        {"content": "Pedir al ERP los pedidos pendientes de Ernst Handel", "status": "in_progress"},
        {"content": "Pedir a producción el estado de esos pedidos", "status": "pending"},
    ]}, "c1"),
    tool_call("task", {"subagent_type": "erp-agent", "description": "Dame los pedidos pendientes del cliente Ernst Handel"}, "c2"),
    # Agente ERP: busca el cliente y sus pedidos pendientes.
    tool_call("search_customers", {"query": "Ernst Handel"}, "e1"),
    tool_call("get_customer_orders", {"customer_id": "ERNSH", "only_pending": True}, "e2"),
    AIMessage(content="Ernst Handel (ERNSH) tiene 2 pedidos pendientes: 11072 y 11008."),
    # Coordinador: delega en produccion.
    tool_call("task", {"subagent_type": "production-agent", "description": "Estado de fabricación de los pedidos 11072 y 11008"}, "c3"),
    # Agente de produccion.
    tool_call("get_production_status", {"order_ids": [11072, 11008]}, "p1"),
    AIMessage(content="11072 bloqueado por falta de materia prima; 11008 retrasado 3 días."),
    # Coordinador: respuesta final.
    AIMessage(content="Ernst Handel tiene 2 pedidos pendientes: el 11072 está bloqueado y el 11008 va retrasado."),
]


def test_question_crossing_erp_and_production(sources):
    service, model = make_service(ERNST_SCRIPT)
    result = service.ask("¿Qué pedidos pendientes tiene Ernst Handel y en qué estado están?")

    assert result.answer.startswith("Ernst Handel tiene 2 pedidos pendientes")
    assert result.sources == ["ERP", "Producción"]
    assert len(model.received) == len(ERNST_SCRIPT)

    # Los pasos son las llamadas reales, con el agente que hizo cada una.
    assert [(step["agent"], step["tool"]) for step in result.steps] == [
        ("coordinator", "write_todos"),
        ("coordinator", "task"),
        ("erp-agent", "search_customers"),
        ("erp-agent", "get_customer_orders"),
        ("coordinator", "task"),
        ("production-agent", "get_production_status"),
    ]
    assert all(step["ok"] for step in result.steps)

    # El razonamiento incluye datos reales devueltos por las tools, no texto del modelo.
    reasoning = "\n".join(result.reasoning)
    assert result.reasoning[0].startswith("Plan: (1) Pedir al ERP")
    assert "delega en el agente ERP" in reasoning
    assert "Ernst Handel (ERNSH)" in reasoning
    assert "→ 2 (11072, 11008)" in reasoning
    assert "11072: bloqueado" in reasoning and "11008: retrasado" in reasoning
    assert result.reasoning[-1] == "Coordinador: combina los resultados de ERP y Producción y redacta la respuesta"


def test_subagent_only_sees_its_task_not_the_conversation(sources):
    service, model = make_service(ERNST_SCRIPT)
    service.ask("¿Qué pedidos pendientes tiene Ernst Handel y en qué estado están?")

    erp_first_call = model.received[2]
    assert "agente del ERP" in erp_first_call[0].content
    assert [message.content for message in erp_first_call[1:]] == ["Dame los pedidos pendientes del cliente Ernst Handel"]

    # Y el coordinador solo recibe del subagente su respuesta final, no sus pasos.
    coordinator_after_erp = model.received[5]
    tool_results = [message.content for message in coordinator_after_erp if isinstance(message, ToolMessage)]
    assert "Ernst Handel (ERNSH) tiene 2 pedidos pendientes: 11072 y 11008." in tool_results
    assert not any("customer_id" in content for content in tool_results)


def test_memory_keeps_the_conversation_of_a_session(sources):
    service, model = make_service(ERNST_SCRIPT + [AIMessage(content="El bloqueado es el 11072.")])
    first = service.ask("¿Qué pedidos pendientes tiene Ernst Handel?", session_id="s1")
    second = service.ask("¿Y cuáles de esos están bloqueados?", session_id="s1")

    assert first.session_id == second.session_id == "s1"
    assert second.answer == "El bloqueado es el 11072."
    questions = [message.content for message in model.received[-1] if isinstance(message, HumanMessage)]
    assert questions == ["¿Qué pedidos pendientes tiene Ernst Handel?", "¿Y cuáles de esos están bloqueados?"]
    # La segunda pregunta no ha consultado nada: se responde con lo ya hablado.
    assert second.sources == []
    assert second.steps == []


def test_sessions_do_not_share_memory(sources):
    service, model = make_service([AIMessage(content="uno"), AIMessage(content="dos")])
    service.ask("Pregunta de la sesión A", session_id="a")
    service.ask("Pregunta de la sesión B", session_id="b")
    questions = [message.content for message in model.received[-1] if isinstance(message, HumanMessage)]
    assert questions == ["Pregunta de la sesión B"]


def test_model_only_sees_the_last_interactions(sources):
    total = 8
    service, model = make_service([AIMessage(content=f"respuesta {i}") for i in range(total)])
    for i in range(total):
        service.ask(f"pregunta {i}", session_id="larga")
    questions = [message.content for message in model.received[-1] if isinstance(message, HumanMessage)]
    # La actual y las 5 anteriores (MEMORY_MAX_INTERACTIONS=5).
    assert questions == [f"pregunta {i}" for i in range(2, 8)]


def test_failed_source_is_reported_and_not_listed(erp, monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    down = ProductionClient("http://down", http_client=httpx.Client(transport=httpx.MockTransport(refuse)))
    monkeypatch.setattr(production_tools, "get_production_client", lambda: down)

    service, _ = make_service([
        tool_call("task", {"subagent_type": "production-agent", "description": "Pedidos bloqueados"}, "c1"),
        tool_call("list_production_orders", {"status": "bloqueado"}, "p1"),
        AIMessage(content="El sistema de producción no responde."),
        AIMessage(content="No puedo consultar producción ahora mismo."),
    ])
    result = service.ask("¿Qué pedidos están bloqueados?")

    assert result.sources == []
    assert "no ha podido obtener datos" in "\n".join(result.reasoning)
    assert result.steps[-1]["ok"] is False


# --- Piezas sueltas ---


def test_every_data_tool_has_a_source():
    tools = {tool.name for subagent in build_subagents() for tool in subagent["tools"]}
    assert tools == set(SOURCE_BY_TOOL)


def test_keep_recent_turns_cuts_at_the_start_of_an_interaction():
    messages = []
    for i in range(4):
        messages += [HumanMessage(f"q{i}"), tool_call("task", {}, f"c{i}"), ToolMessage("dato", tool_call_id=f"c{i}"), AIMessage(f"a{i}")]
    kept = keep_recent_turns(messages, previous_turns=1)
    assert [m.content for m in kept if isinstance(m, HumanMessage)] == ["q2", "q3"]
    assert isinstance(kept[0], HumanMessage)
    assert len(kept) == 8
    assert keep_recent_turns(messages, previous_turns=10) == messages


def test_sources_name_documents_and_pages():
    step = TraceStep(
        agent="documents-agent", tool="search_documents", args={"query": "penalización"},
        result={"results": [
            {"document": "contrato.pdf", "page": 2, "relevance": 0.8, "text": "..."},
            {"document": "contrato.pdf", "page": 1, "relevance": 0.7, "text": "..."},
        ]},
    )
    assert build_sources([step]) == ["Documento: contrato.pdf (pág. 1, 2)"]
    reasoning = build_reasoning([step])
    assert "busca «penalización» en los documentos → 2 fragmentos" in reasoning[0]
    assert reasoning[-1] == "Coordinador: redacta la respuesta con los datos de Documentos"


def test_reasoning_without_any_tool():
    assert build_sources([]) == []
    assert build_reasoning([]) == ["Coordinador: responde sin consultar ninguna fuente de datos"]
