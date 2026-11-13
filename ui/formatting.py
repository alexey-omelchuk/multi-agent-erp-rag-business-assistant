"""Convierte las respuestas de la API en texto para el chat. Sin dependencias de Chainlit."""


def format_reasoning(reasoning: list[str]) -> str:
    return "\n".join(f"{number}. {step}" for number, step in enumerate(reasoning, start=1))


def format_answer(response: dict) -> str:
    sources = response.get("sources") or []
    footer = "**Fuentes:** " + (" · ".join(sources) if sources else "ninguna (respondido con la conversación)")
    seconds = response.get("duration_ms", 0) / 1000
    return f"{response['answer']}\n\n---\n{footer}  \n*{len(response.get('steps', []))} llamadas a herramientas · {seconds:.1f} s*"


def format_upload(document: dict) -> str:
    return f"Documento **{document['document']}** indexado: {document['pages']} páginas, {document['chunks']} fragmentos."


def format_error(status_code: int, detail: str) -> str:
    # El detalle va en un bloque de codigo: asi el chat lo muestra literal y no
    # interpreta como formato textos como "openai:gpt-5.6-luna".
    return f"**Error {status_code}.** No se ha podido completar la operación.\n\n```text\n{detail}\n```"
