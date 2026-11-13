"""Dobles de prueba para ejecutar los agentes sin un modelo de lenguaje real."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    """Respuesta del modelo que pide ejecutar una tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


class ScriptedChatModel(BaseChatModel):
    """Modelo falso que devuelve, en orden, las respuestas de un guion.

    Coordinador y subagentes comparten el mismo modelo, asi que el guion es la
    secuencia completa de respuestas de todos ellos. Guarda lo que recibio en
    cada llamada para poder comprobarlo en los tests.
    """

    script: list[AIMessage]
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        if len(self.received) >= len(self.script):
            raise AssertionError("El agente ha llamado al modelo mas veces de las previstas en el guion.")
        self.received.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.script[len(self.received) - 1])])
