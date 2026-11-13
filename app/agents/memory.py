"""Memoria conversacional: cuanta conversacion anterior ve el modelo.

La conversacion completa de cada sesion la guarda el checkpointer. Este
middleware decide que parte se envia al modelo en cada llamada: la pregunta
actual y las N interacciones anteriores. Asi una sesion larga no hace crecer
sin limite el coste ni el ruido.
"""

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AnyMessage, HumanMessage


def keep_recent_turns(messages: list[AnyMessage], previous_turns: int) -> list[AnyMessage]:
    """Devuelve la interaccion actual y las `previous_turns` anteriores.

    Una interaccion empieza en un mensaje del usuario e incluye todo lo que
    viene despues (llamadas a tools y respuesta). Se corta siempre al inicio de
    una interaccion, para no separar una llamada a tool de su resultado.
    """
    starts = [index for index, message in enumerate(messages) if isinstance(message, HumanMessage)]
    if len(starts) <= previous_turns + 1:
        return messages
    return messages[starts[-(previous_turns + 1)] :]


class RecentTurnsMiddleware(AgentMiddleware):
    """Envia al modelo solo las ultimas interacciones de la conversacion."""

    def __init__(self, previous_turns: int):
        super().__init__()
        self.previous_turns = previous_turns

    def wrap_model_call(self, request, handler):
        return handler(request.override(messages=keep_recent_turns(request.messages, self.previous_turns)))

    async def awrap_model_call(self, request, handler):
        return await handler(request.override(messages=keep_recent_turns(request.messages, self.previous_turns)))
