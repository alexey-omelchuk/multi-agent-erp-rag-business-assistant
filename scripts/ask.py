"""Hace preguntas al sistema multi-agente desde la terminal.

Necesita un modelo configurado en .env (MODEL y la clave del proveedor), la
API de produccion arrancada y, para preguntas sobre documentos, los PDF
indexados (scripts/try_rag.py).

Uso con Docker:
    docker compose run --rm cli python scripts/ask.py "¿Qué pedidos están bloqueados y por qué?"
    docker compose run --rm cli python scripts/ask.py          (lanza la demo completa)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.model import ModelNotConfiguredError  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.services.query_service import get_query_service  # noqa: E402

# Las cuatro preguntas del enunciado, dos de seguimiento (memoria) y una de documentos.
DEMO = [
    "¿Qué pedidos pendientes tiene el cliente Ernst Handel y en qué estado de producción están?",
    "¿Y cuál es el impacto económico de esos pedidos?",
    "¿Qué pedidos están bloqueados y cuál es el motivo?",
    "¿Qué clientes tienen pedidos retrasados por problemas de producción?",
    "Dame un resumen del estado de los pedidos de este mes",
    "¿Hay alguna penalización por retrasos en el contrato de Ernst Handel?",
]


def ask(question: str, session_id: str) -> None:
    result = get_query_service().ask(question, session_id)
    print(f"\n{'=' * 100}\nPREGUNTA: {question}\n")
    print(f"RESPUESTA:\n{result.answer}\n")
    print(f"FUENTES: {result.sources}\n")
    print("RAZONAMIENTO:")
    for number, step in enumerate(result.reasoning, start=1):
        print(f"  {number}. {step}")
    print(f"\n({result.duration_ms / 1000:.1f} s, {len(result.steps)} llamadas a tools)")


if __name__ == "__main__":
    setup_logging()
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEMO
    try:
        for question in questions:
            ask(question, session_id="demo")
    except ModelNotConfiguredError as exc:
        raise SystemExit(f"ERROR: {exc}")
