"""El modelo de lenguaje. Se elige con la variable MODEL ("proveedor:modelo").

Ejemplos: "openai:gpt-5.6-luna", "azure_openai:gpt-5.6-luna", "anthropic:claude-haiku-4-5".
"""

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings


# Proveedores cuyo cliente admite "timeout" y "max_retries".
_PROVIDERS_WITH_TIMEOUT = {"openai", "azure_openai", "anthropic"}


class ModelNotConfiguredError(RuntimeError):
    """No se puede crear el modelo: falta la clave de API o MODEL no es valido."""


def _azure_options(settings: Settings, model_name: str) -> dict[str, Any]:
    """Parametros de conexion de Azure OpenAI, leidos de las variables AZURE_OPENAI_*."""
    missing = [
        variable
        for variable, value in {
            "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
            "AZURE_OPENAI_BASE_URL": settings.azure_openai_base_url,
            "AZURE_OPENAI_API_VERSION": settings.azure_openai_api_version,
        }.items()
        if not value
    ]
    if missing:
        raise ModelNotConfiguredError(f"Para usar Azure OpenAI faltan en .env: {', '.join(missing)}.")
    return {
        "azure_endpoint": settings.azure_openai_base_url,
        "api_key": settings.azure_openai_api_key.get_secret_value(),
        "api_version": settings.azure_openai_api_version,
        # En Azure se llama al "deployment", que puede tener otro nombre que el modelo.
        "azure_deployment": settings.azure_openai_model_deployment_name or model_name,
    }


def get_chat_model() -> BaseChatModel:
    settings = get_settings()
    model = settings.model
    provider, _, model_name = model.partition(":")

    options: dict[str, Any] = {}
    # La temperatura solo se envia si se ha configurado (MODEL_TEMPERATURE): los
    # modelos de razonamiento no suelen admitir una fija.
    if settings.model_temperature is not None:
        options["temperature"] = settings.model_temperature
    if provider in _PROVIDERS_WITH_TIMEOUT:
        # Si el proveedor no responde, la llamada falla pronto y con un error
        # claro, en lugar de dejar la consulta colgada.
        options["timeout"] = settings.model_timeout_seconds
        options["max_retries"] = settings.model_max_retries
    if settings.model_reasoning_effort:
        options["reasoning_effort"] = settings.model_reasoning_effort
    if provider == "azure_openai":
        options.update(_azure_options(settings, model_name))

    try:
        return init_chat_model(model, **options)
    except Exception as exc:
        raise ModelNotConfiguredError(
            f"No se ha podido iniciar el modelo '{model}'. Revisa en .env la variable MODEL "
            f"y la clave de API de ese proveedor. Detalle: {exc}"
        ) from exc
