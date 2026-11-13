"""El agente coordinador: un Deep Agent que planifica y delega.

Agent = Model + Harness. Aqui se monta el harness:
  - prompt del coordinador (su papel y sus reglas)
  - subagentes (a quien puede delegar, con la tool `task`)
  - planificacion (tool `write_todos`)
  - memoria (checkpointer + ventana de interacciones recientes)
El coordinador no recibe ninguna tool de datos: para saber algo tiene que delegar.
"""

from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.memory import RecentTurnsMiddleware
from app.agents.model import get_chat_model
from app.agents.prompts import coordinator_prompt
from app.agents.subagents import build_subagents
from app.config import get_settings

COORDINATOR = "coordinator"


def build_coordinator(
    model: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    settings = get_settings()
    return create_deep_agent(
        model=model or get_chat_model(),
        name=COORDINATOR,
        system_prompt=coordinator_prompt(),
        subagents=build_subagents(),
        middleware=[
            TodoListMiddleware(),
            RecentTurnsMiddleware(previous_turns=settings.memory_max_interactions),
        ],
        checkpointer=checkpointer,
    )
