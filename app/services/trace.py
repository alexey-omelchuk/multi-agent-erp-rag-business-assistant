"""Trazabilidad: registra lo que el sistema ha hecho de verdad en cada pregunta.

`sources` y `reasoning` no los redacta el modelo: se construyen a partir de
las llamadas reales a las tools. Si una fuente aparece en la respuesta es
porque se ha consultado, y cada paso del razonamiento es una accion que ha
ocurrido, con sus argumentos y su resultado.

Como funciona: LangChain avisa a un "callback handler" cada vez que empieza o
termina una tool. El aviso llega tambien desde los subagentes, e indica que
agente la ha llamado.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from app.agents.coordinator import COORDINATOR
from app.agents.prompts import DOCUMENTS_AGENT, ERP_AGENT, PRODUCTION_AGENT
from app.tools.documents import DOCUMENT_TOOLS
from app.tools.erp import ERP_TOOLS
from app.tools.production import PRODUCTION_TOOLS

logger = logging.getLogger(__name__)

# De que fuente es cada tool. Se deduce de las listas de tools: al anadir una
# tool nueva a una fuente, queda registrada sola.
SOURCE_BY_TOOL: dict[str, str] = {
    **{tool.name: "ERP" for tool in ERP_TOOLS},
    **{tool.name: "Producción" for tool in PRODUCTION_TOOLS},
    **{tool.name: "Documentos" for tool in DOCUMENT_TOOLS},
}

AGENT_LABELS = {
    COORDINATOR: "Coordinador",
    ERP_AGENT: "Agente ERP",
    PRODUCTION_AGENT: "Agente de producción",
    DOCUMENTS_AGENT: "Agente de documentos",
}

PLAN_TOOL = "write_todos"
DELEGATE_TOOL = "task"


@dataclass
class TraceStep:
    """Una llamada a una tool: quien, que, con que argumentos y que obtuvo."""

    agent: str
    tool: str
    args: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: int = 0

    @property
    def source(self) -> str | None:
        return SOURCE_BY_TOOL.get(self.tool)

    @property
    def failed(self) -> bool:
        return self.error is not None or (isinstance(self.result, dict) and "error" in self.result)

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "tool": self.tool,
            "source": self.source,
            "args": self.args,
            "ok": not self.failed,
            "duration_ms": self.duration_ms,
        }


def _parse_output(output: Any) -> Any:
    """Convierte la salida de una tool (mensaje con JSON) en datos de Python."""
    update = getattr(output, "update", None)
    if isinstance(update, dict) and update.get("messages"):  # tools que devuelven un Command
        output = update["messages"][-1]
    content = getattr(output, "content", output)
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


class TraceRecorder(BaseCallbackHandler):
    """Apunta cada llamada a una tool, en el orden en que empieza."""

    def __init__(self) -> None:
        self.steps: list[TraceStep] = []
        self._running: dict[UUID, tuple[TraceStep, float]] = {}
        self._lock = threading.Lock()  # las tools pueden ejecutarse en paralelo

    def on_tool_start(self, serialized, input_str, *, run_id, metadata=None, inputs=None, **kwargs) -> None:
        step = TraceStep(
            agent=(metadata or {}).get("lc_agent_name", COORDINATOR),
            tool=(serialized or {}).get("name") or kwargs.get("name", "?"),
            # Solo los argumentos que eligio el modelo, no los internos del framework.
            args={key: value for key, value in (inputs or {}).items() if key not in ("runtime", "state", "config")},
        )
        with self._lock:
            self.steps.append(step)
            self._running[run_id] = (step, time.perf_counter())
        logger.info("tool_start agent=%s tool=%s args=%s", step.agent, step.tool, json.dumps(step.args, ensure_ascii=False, default=str))

    def _finish(self, run_id: UUID) -> TraceStep | None:
        with self._lock:
            entry = self._running.pop(run_id, None)
        if entry is None:
            return None
        step, started = entry
        step.duration_ms = round((time.perf_counter() - started) * 1000)
        return step

    def on_tool_end(self, output, *, run_id, **kwargs) -> None:
        if step := self._finish(run_id):
            step.result = _parse_output(output)
            level = logging.WARNING if step.failed else logging.INFO
            logger.log(level, "tool_end agent=%s tool=%s ok=%s ms=%d", step.agent, step.tool, not step.failed, step.duration_ms)

    def on_tool_error(self, error, *, run_id, **kwargs) -> None:
        if step := self._finish(run_id):
            step.error = str(error)
            logger.warning("tool_error agent=%s tool=%s error=%s", step.agent, step.tool, step.error)


# --- De la traza a "sources" ---


def build_sources(steps: list[TraceStep]) -> list[str]:
    """Fuentes consultadas con exito, sin repetir y en orden de uso.

    De los documentos se indica ademas cuales se han leido y en que paginas.
    """
    sources: list[str] = []  # en orden de primer uso
    pages: dict[str, set[int]] = {}  # paginas leidas de cada documento, sumando todas las busquedas
    for step in steps:
        if step.source is None or step.failed:
            continue
        if step.source not in sources:
            sources.append(step.source)
        if step.tool == "search_documents" and isinstance(step.result, dict):
            for hit in step.result.get("results", []):
                pages.setdefault(hit["document"], set()).add(hit["page"])

    if not pages:
        return sources
    # Si se han leido fragmentos, "Documentos" se sustituye por cada documento
    # concreto, una sola vez, con todas sus paginas.
    documents = [
        f"Documento: {document} (pág. {', '.join(str(page) for page in sorted(found))})"
        for document, found in pages.items()
    ]
    position = sources.index("Documentos")
    return sources[:position] + documents + sources[position + 1 :]


# --- De la traza a "reasoning" ---


def _count(result: Any, key: str) -> int:
    return len(result.get(key, [])) if isinstance(result, dict) else 0


def _ids(orders: list[dict]) -> str:
    return ", ".join(str(order["order_id"]) for order in orders) or "ninguno"


def _describe_search_customers(args: dict, result: Any) -> str:
    names = ", ".join(f"{c['company_name']} ({c['customer_id']})" for c in result.get("customers", []))
    return f"busca el cliente «{args.get('query')}» en el ERP → {names or 'sin coincidencias'}"


def _describe_list_customers(args: dict, result: Any) -> str:
    scope = f" de {args['country']}" if args.get("country") else ""
    return f"lista los clientes{scope} con sus pedidos e importe en el ERP → {result.get('total', 0)} clientes, {result.get('total_orders', 0)} pedidos"


def _describe_customer_orders(args: dict, result: Any) -> str:
    kind = "pedidos pendientes" if args.get("only_pending") else "pedidos"
    return f"consulta los {kind} del cliente {args.get('customer_id')} en el ERP → {result.get('total', 0)} ({_ids(result.get('orders', []))})"


def _describe_pending_orders(args: dict, result: Any) -> str:
    return f"consulta todos los pedidos pendientes de envío en el ERP → {result.get('total', 0)} pedidos"


def _describe_orders_by_id(args: dict, result: Any) -> str:
    customers = sorted({order["customer_name"] or order["customer_id"] for order in result.get("orders", [])})
    return f"consulta en el ERP el cliente e importe de los pedidos {args.get('order_ids')} → {len(customers)} clientes: {', '.join(customers)}"


def _describe_orders_summary(args: dict, result: Any) -> str:
    return (
        f"resume los pedidos del {result.get('start_date')} al {result.get('end_date')} en el ERP → "
        f"{result.get('total_orders')} pedidos, importe {result.get('total_amount')}, {result.get('pending_orders')} pendientes"
    )


def _describe_production_status(args: dict, result: Any) -> str:
    states = ", ".join(f"{order['order_id']}: {order['status']}" for order in result.get("orders", []))
    return f"consulta en producción el estado de los pedidos {args.get('order_ids')} → {states or 'sin datos'}"


def _describe_list_production(args: dict, result: Any) -> str:
    return f"lista en producción los pedidos en estado «{args.get('status')}» → {result.get('total', 0)} ({_ids(result.get('orders', []))})"


def _describe_production_summary(args: dict, result: Any) -> str:
    counts = ", ".join(f"{status}: {count}" for status, count in result.get("by_status", {}).items())
    return f"consulta en producción el recuento de pedidos por estado → {counts}"


def _describe_search_documents(args: dict, result: Any) -> str:
    scope = f" en {args['document']}" if args.get("document") else " en los documentos"
    hits = [f"{hit['document']} pág. {hit['page']}" for hit in result.get("results", [])]
    found = f"{len(hits)} fragmentos ({', '.join(dict.fromkeys(hits))})" if hits else "sin fragmentos relevantes"
    return f"busca «{args.get('query')}»{scope} → {found}"


def _describe_list_documents(args: dict, result: Any) -> str:
    return f"lista los documentos indexados → {_count(result, 'documents')}"


_DESCRIBERS = {
    "search_customers": _describe_search_customers,
    "list_customers": _describe_list_customers,
    "get_customer_orders": _describe_customer_orders,
    "get_pending_orders": _describe_pending_orders,
    "get_orders_by_id": _describe_orders_by_id,
    "get_orders_summary": _describe_orders_summary,
    "get_production_status": _describe_production_status,
    "list_production_orders": _describe_list_production,
    "get_production_summary": _describe_production_summary,
    "search_documents": _describe_search_documents,
    "list_documents": _describe_list_documents,
}


def _describe(step: TraceStep) -> str:
    agent = AGENT_LABELS.get(step.agent, step.agent)

    if step.tool == DELEGATE_TOOL:
        target = AGENT_LABELS.get(step.args.get("subagent_type", ""), step.args.get("subagent_type", "?"))
        task = " ".join(str(step.args.get("description", "")).split())
        return f"{agent}: delega en el {target[0].lower() + target[1:]} → «{task[:220]}»"

    if step.error:
        return f"{agent}: la herramienta {step.tool} ha fallado ({step.error})"
    if isinstance(step.result, str) and "limit" in step.result.lower() and step.source:
        return f"{agent}: ha alcanzado el límite de llamadas a herramientas de esta consulta"
    if isinstance(step.result, dict) and "error" in step.result:
        return f"{agent}: {step.tool} no ha podido obtener datos ({step.result['error']})"

    describer = _DESCRIBERS.get(step.tool)
    if describer and isinstance(step.result, dict):
        return f"{agent}: {describer(step.args, step.result)}"
    return f"{agent}: usa la herramienta {step.tool}"


def build_reasoning(steps: list[TraceStep]) -> list[str]:
    """Pasos ejecutados, en orden y en lenguaje natural."""
    reasoning: list[str] = []
    plan_shown = False
    for step in steps:
        if step.tool == PLAN_TOOL:
            # El plan se muestra una vez; las actualizaciones posteriores solo marcan tareas hechas.
            if not plan_shown:
                todos = [todo.get("content", "") for todo in step.args.get("todos", [])]
                reasoning.append("Plan: " + "; ".join(f"({i}) {todo}" for i, todo in enumerate(todos, start=1)))
                plan_shown = True
            continue
        reasoning.append(_describe(step))

    used = build_sources(steps)
    kinds = list(dict.fromkeys("Documentos" if name.startswith("Documento") else name for name in used))
    if len(kinds) > 1:
        reasoning.append(f"Coordinador: combina los resultados de {', '.join(kinds[:-1])} y {kinds[-1]} y redacta la respuesta")
    elif kinds:
        reasoning.append(f"Coordinador: redacta la respuesta con los datos de {kinds[0]}")
    else:
        reasoning.append("Coordinador: responde sin consultar ninguna fuente de datos")
    return reasoning
