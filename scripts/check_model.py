"""Comprueba que el modelo configurado responde y sabe llamar a herramientas.

Es lo primero que conviene lanzar tras poner las claves en .env: tarda unos
segundos y, si algo falla, el error dice exactamente que (clave, version de la
API, nombre del deployment...).

Uso con Docker:
    docker compose run --rm cli python scripts/check_model.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.tools import tool  # noqa: E402

from app.agents.model import ModelNotConfiguredError, get_chat_model  # noqa: E402
from app.config import get_settings  # noqa: E402


@tool
def get_order_status(order_id: int) -> str:
    """Devuelve el estado de fabricacion de un pedido."""
    return "bloqueado"


if __name__ == "__main__":
    print(f"Modelo: {get_settings().model}")
    try:
        model = get_chat_model()
    except ModelNotConfiguredError as exc:
        raise SystemExit(f"ERROR al crear el modelo: {exc}")

    try:
        started = time.perf_counter()
        reply = model.invoke("Responde solo con la palabra: listo")
        print(f"1) Respuesta de texto ({time.perf_counter() - started:.1f} s): {reply.text.strip()!r}")

        started = time.perf_counter()
        reply = model.bind_tools([get_order_status]).invoke("¿En qué estado está el pedido 11039?")
        calls = [(call["name"], call["args"]) for call in reply.tool_calls]
        print(f"2) Llamada a herramienta ({time.perf_counter() - started:.1f} s): {calls}")
    except Exception as exc:
        raise SystemExit(f"ERROR al llamar al modelo: {type(exc).__name__}: {exc}")

    if not calls:
        raise SystemExit("AVISO: el modelo responde, pero no ha llamado a la herramienta.")
    print("OK: el modelo responde y usa herramientas.")
