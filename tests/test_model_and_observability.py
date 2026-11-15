"""Configuracion del modelo (OpenAI, Azure) y envio opcional de trazas a Langfuse.

Ninguno de estos tests llama al proveedor: solo comprueban como se construye
el cliente a partir de las variables de entorno.
"""

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage

from app import observability
from app.agents import model as model_module
from app.agents.model import ModelNotConfiguredError, get_chat_model
from app.config import get_settings
from app.services import query_service
from tests.test_agents import make_service, sources  # noqa: F401  (fixture)


@pytest.fixture
def settings(monkeypatch):
    """Ajustes limpios para cada test (get_settings guarda una copia en cache)."""
    for variable in ("MODEL", "MODEL_TEMPERATURE", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL",
                     "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_MODEL_DEPLOYMENT_NAME",
                     "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    get_settings.cache_clear()
    observability.get_langfuse_handler.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()
    observability.get_langfuse_handler.cache_clear()


def test_azure_model_uses_the_azure_variables(settings):
    settings.setenv("MODEL", "azure_openai:gpt-5.6-luna")
    settings.setenv("AZURE_OPENAI_API_KEY", "clave-de-prueba")
    settings.setenv("AZURE_OPENAI_BASE_URL", "https://recurso.openai.azure.com/")
    settings.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    settings.setenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", "mi-deployment")

    chat_model = get_chat_model()

    assert type(chat_model).__name__ == "AzureChatOpenAI"
    assert chat_model.deployment_name == "mi-deployment"
    assert chat_model.openai_api_version == "2024-12-01-preview"
    assert chat_model.azure_endpoint == "https://recurso.openai.azure.com/"


def test_azure_without_variables_explains_what_is_missing(settings):
    settings.setenv("MODEL", "azure_openai:gpt-5.6-luna")
    with pytest.raises(ModelNotConfiguredError, match="AZURE_OPENAI_API_KEY, AZURE_OPENAI_BASE_URL"):
        get_chat_model()


def test_temperature_is_only_sent_when_configured(settings, monkeypatch):
    received = {}
    monkeypatch.setattr(model_module, "init_chat_model", lambda model, **options: received.update(options))
    settings.setenv("MODEL", "openai:gpt-5.6-luna")

    get_chat_model()
    assert "temperature" not in received

    settings.setenv("MODEL_TEMPERATURE", "0")
    get_settings.cache_clear()
    get_chat_model()
    assert received["temperature"] == 0


def test_missing_key_gives_a_clear_error(settings):
    settings.setenv("MODEL", "openai:gpt-5.6-luna")
    with pytest.raises(ModelNotConfiguredError, match="Revisa en .env"):
        get_chat_model()


# --- Langfuse ---


def test_langfuse_is_off_without_keys(settings):
    assert observability.get_langfuse_handler() is None
    observability.flush_traces()  # no hace nada y no falla


def test_langfuse_handler_is_created_with_keys(settings):
    settings.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    settings.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    settings.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:9")  # nadie escucha: no debe importar
    handler = observability.get_langfuse_handler()
    assert isinstance(handler, BaseCallbackHandler)


class Spy(BaseCallbackHandler):
    def __init__(self):
        self.tools: list[str] = []
        self.metadata: list[dict] = []

    def on_chain_start(self, serialized, inputs, *, metadata=None, **kwargs):
        self.metadata.append(metadata or {})

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.tools.append(serialized.get("name"))


def test_query_sends_the_execution_and_the_session_to_langfuse(sources, monkeypatch):
    spy = Spy()
    monkeypatch.setattr(query_service, "get_langfuse_handler", lambda: spy)
    from tests.test_agents import ERNST_SCRIPT

    service, _ = make_service(ERNST_SCRIPT)
    service.ask("¿Qué pedidos pendientes tiene Ernst Handel?", session_id="sesion-1")

    assert spy.tools == ["write_todos", "task", "search_customers", "get_customer_orders", "task", "get_production_status"]
    assert spy.metadata[0]["langfuse_session_id"] == "sesion-1"


def test_query_works_without_langfuse(sources, monkeypatch):
    monkeypatch.setattr(query_service, "get_langfuse_handler", lambda: None)
    service, _ = make_service([AIMessage(content="hola")])
    assert service.ask("pregunta de prueba").answer == "hola"
