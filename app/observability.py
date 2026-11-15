"""Envio de trazas a Langfuse (opcional).

La trazabilidad de cada respuesta (sources y reasoning) la genera siempre
app/services/trace.py. Langfuse anade una vista detallada para quien opera el
sistema: cada llamada al modelo y a cada tool, con sus entradas, salidas,
tokens y tiempos, agrupadas por conversacion.

Se activa solo si estan LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY. Si Langfuse
no esta disponible, las consultas funcionan igual: solo se pierde la traza.
"""

import logging
from functools import lru_cache

from langchain_core.callbacks import BaseCallbackHandler

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_langfuse_handler() -> BaseCallbackHandler | None:
    """Callback de LangChain que envia la ejecucion a Langfuse, o None si no esta configurado."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        # Crea el cliente una vez; el CallbackHandler lo reutiliza por su clave publica.
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=settings.langfuse_base_url,
        )
        handler = CallbackHandler(public_key=settings.langfuse_public_key)
    except Exception:
        logger.exception("langfuse_disabled: no se ha podido iniciar el cliente")
        return None
    logger.info("langfuse_enabled url=%s", settings.langfuse_base_url)
    return handler


def flush_traces() -> None:
    """Envia las trazas pendientes. Necesario antes de terminar un proceso corto (scripts)."""
    if get_langfuse_handler() is None:
        return
    try:
        from langfuse import get_client

        get_client(public_key=get_settings().langfuse_public_key).flush()
    except Exception:
        logger.warning("langfuse_flush_failed", exc_info=True)
