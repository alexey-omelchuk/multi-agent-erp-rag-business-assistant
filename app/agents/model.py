"""El modelo de lenguaje. Se elige con la variable MODEL ("proveedor:modelo")."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import get_settings


class ModelNotConfiguredError(RuntimeError):
    """No se puede crear el modelo: falta la clave de API o MODEL no es valido."""


def get_chat_model() -> BaseChatModel:
    model = get_settings().model
    try:
        # temperature=0: ante la misma pregunta, el comportamiento mas repetible posible.
        return init_chat_model(model, temperature=0)
    except Exception as exc:
        raise ModelNotConfiguredError(
            f"No se ha podido iniciar el modelo '{model}'. Revisa en .env la variable MODEL "
            f"y la clave de API de ese proveedor. Detalle: {exc}"
        ) from exc
