"""Servicio de consultas: ejecuta el sistema multi-agente y arma la respuesta.

Es el unico punto de entrada a los agentes. La API, la interfaz y los scripts
llaman a QueryService.ask() y reciben siempre lo mismo: respuesta, fuentes,
razonamiento y pasos.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.coordinator import build_coordinator
from app.observability import get_langfuse_handler
from app.services.trace import TraceRecorder, build_reasoning, build_sources

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    answer: str
    sources: list[str]
    reasoning: list[str]
    session_id: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0


def _text(message: Any) -> str:
    """Texto de un mensaje del modelo, venga como cadena o como bloques de contenido."""
    text = getattr(message, "text", None)
    return (text if isinstance(text, str) else str(message.content)).strip()


class QueryService:
    def __init__(self, agent: CompiledStateGraph):
        self._agent = agent

    def ask(self, question: str, session_id: str | None = None, documents: list[str] | None = None) -> QueryResult:
        """Responde una pregunta. Con el mismo session_id, recuerda la conversacion.

        `documents` son los PDF adjuntos a este mensaje: se le indican al agente
        para que sepa que la pregunta puede referirse a ellos.
        """
        session_id = session_id or uuid.uuid4().hex
        content = question
        if documents:
            content += f"\n\n[Documentos adjuntos a este mensaje, ya indexados: {', '.join(documents)}]"
        recorder = TraceRecorder()
        started = time.perf_counter()
        logger.info("query_start session=%s question=%r", session_id, question)

        # El recorder recibe cada llamada a tool, tambien las de los subagentes.
        # Si Langfuse esta configurado, recibe ademas toda la ejecucion.
        callbacks = [recorder]
        if (langfuse := get_langfuse_handler()) is not None:
            callbacks.append(langfuse)

        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": content}]},
            config={
                # thread_id: el checkpointer guarda y recupera la conversacion de esta sesion.
                "configurable": {"thread_id": session_id},
                "callbacks": callbacks,
                # Langfuse agrupa las trazas de una misma conversacion por este identificador.
                "metadata": {"langfuse_session_id": session_id},
                "run_name": "consulta",
            },
        )

        query_result = QueryResult(
            answer=_text(result["messages"][-1]),
            sources=build_sources(recorder.steps),
            reasoning=build_reasoning(recorder.steps),
            session_id=session_id,
            steps=[step.as_dict() for step in recorder.steps],
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        logger.info(
            "query_end session=%s sources=%s steps=%d ms=%d",
            session_id,
            query_result.sources,
            len(query_result.steps),
            query_result.duration_ms,
        )
        return query_result


@lru_cache
def get_query_service() -> QueryService:
    # InMemorySaver: la memoria de las sesiones vive mientras el proceso este arrancado.
    return QueryService(build_coordinator(checkpointer=InMemorySaver()))
