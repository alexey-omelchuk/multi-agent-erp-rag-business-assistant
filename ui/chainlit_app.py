"""Interfaz de chat (Chainlit).

No habla con los agentes directamente: llama a la API principal por HTTP,
igual que lo haria cualquier otro cliente. Hay una sola puerta de entrada.

Arranque:
    chainlit run ui/chainlit_app.py --host 0.0.0.0 --port 8080
"""

import os
import sys
import uuid
from pathlib import Path

import chainlit as cl
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.formatting import format_answer, format_error, format_reasoning, format_upload  # noqa: E402

API_URL = os.getenv("API_URL", "http://localhost:8000")
# Una pregunta puede encadenar varias llamadas al modelo: se le da margen.
TIMEOUT = httpx.Timeout(300.0, connect=10.0)


@cl.set_starters
async def starters(*_):
    return [
        cl.Starter(label="Pedidos pendientes de un cliente", message="¿Qué pedidos pendientes tiene el cliente Ernst Handel y en qué estado de producción están?"),
        cl.Starter(label="Pedidos bloqueados", message="¿Qué pedidos están bloqueados y cuál es el motivo?"),
        cl.Starter(label="Clientes con retrasos", message="¿Qué clientes tienen pedidos retrasados por problemas de producción?"),
        cl.Starter(label="Resumen del mes", message="Dame un resumen del estado de los pedidos de este mes"),
        cl.Starter(label="Penalizaciones del contrato", message="¿Hay alguna penalización por retrasos en el contrato?"),
    ]


@cl.on_chat_start
async def on_chat_start():
    # Un session_id por conversacion: es lo que da memoria a las preguntas encadenadas.
    cl.user_session.set("session_id", uuid.uuid4().hex)


def _error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text


async def _upload_pdfs(client: httpx.AsyncClient, elements: list) -> None:
    for element in elements:
        if not (element.name or "").lower().endswith(".pdf"):
            await cl.Message(content=f"**{element.name}** no es un PDF; se ha ignorado.").send()
            continue
        with open(element.path, "rb") as pdf:
            response = await client.post("/api/documents", files={"file": (element.name, pdf, "application/pdf")})
        if response.status_code == 201:
            await cl.Message(content=format_upload(response.json())).send()
        else:
            await cl.Message(content=format_error(response.status_code, _error_detail(response))).send()


async def _ask(client: httpx.AsyncClient, question: str) -> None:
    # El paso queda visible y desplegable: muestra que ha hecho el sistema.
    async with cl.Step(name="Razonamiento", type="run", show_input=False) as step:
        response = await client.post(
            "/api/query",
            json={"question": question, "session_id": cl.user_session.get("session_id")},
        )
        if response.status_code == 200:
            step.output = format_reasoning(response.json()["reasoning"])
        else:
            step.output = "La consulta no se ha completado."

    if response.status_code == 200:
        await cl.Message(content=format_answer(response.json())).send()
    else:
        await cl.Message(content=format_error(response.status_code, _error_detail(response))).send()


@cl.on_message
async def on_message(message: cl.Message):
    try:
        async with httpx.AsyncClient(base_url=API_URL, timeout=TIMEOUT) as client:
            if message.elements:
                await _upload_pdfs(client, message.elements)
            if message.content.strip():
                await _ask(client, message.content.strip())
    except httpx.TimeoutException:
        await cl.Message(
            content="**La consulta ha tardado demasiado y se ha cancelado.** Prueba a acotarla: "
            "un cliente, un país, un periodo o un estado concreto."
        ).send()
    except httpx.HTTPError as exc:
        await cl.Message(content=f"**Error.** No se ha podido conectar con la API ({API_URL}): {type(exc).__name__}").send()
