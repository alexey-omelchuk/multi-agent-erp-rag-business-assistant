"""El modelo de lenguaje. Se elige con la variable MODEL ("proveedor:modelo")."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import get_settings


class ModelNotConfiguredError(RuntimeError):
    """No se puede crear el modelo: falta la clave de API o MODEL no es valido."""


def get_chat_model() -> BaseChatModel:
    settings = get_settings()
    model = settings.model
    # La temperatura solo se envia si se ha configurado (MODEL_TEMPERATURE).
    options = {} if settings.model_temperature is None else {"temperature": settings.model_temperature}
    try:
        return init_chat_model(model, **options)
    except Exception as exc:
        raise ModelNotConfiguredError(
            f"No se ha podido iniciar el modelo '{model}'. Revisa en .env la variable MODEL "
            f"y la clave de API de ese proveedor. Detalle: {exc}"
        ) from exc
