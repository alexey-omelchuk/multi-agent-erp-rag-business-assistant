"""Limites de ejecucion de los agentes.

Un agente decide por si mismo cuantas veces llama a sus tools. Ante una
pregunta demasiado amplia ("todos los clientes y todos sus pedidos") podria
encadenar decenas de llamadas y tardar minutos. Estos middleware lo acotan:

- ToolCallLimitMiddleware: a partir del limite, las llamadas a tools ya no se
  ejecutan y el agente recibe un aviso, de modo que responde con lo que tiene.
- ModelCallLimitMiddleware: tope duro de llamadas al modelo; si se alcanza, el
  agente termina.
"""

from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware, ToolCallLimitMiddleware

from app.config import get_settings

# Con los valores por defecto (8 delegaciones, 10 llamadas por encargo), el peor
# caso de una consulta queda por debajo del tiempo de espera de la interfaz.


def build_limits(coordinator: bool = False) -> list[AgentMiddleware]:
    settings = get_settings()
    max_tool_calls = settings.coordinator_max_tool_calls if coordinator else settings.agent_max_tool_calls
    return [
        ToolCallLimitMiddleware(run_limit=max_tool_calls, exit_behavior="continue"),
        # Margen sobre el limite de tools: las llamadas que solo redactan texto.
        ModelCallLimitMiddleware(run_limit=max_tool_calls + 4, exit_behavior="end"),
    ]
