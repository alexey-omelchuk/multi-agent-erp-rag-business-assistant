"""Esquemas Pydantic de la API: la forma exacta de lo que entra y lo que sale."""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000, description="Pregunta en lenguaje natural")
    session_id: str | None = Field(
        default=None,
        max_length=100,
        description="Identificador de la conversacion. Repite el mismo valor para hacer preguntas encadenadas.",
    )

    documents: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Nombres de los documentos adjuntos a este mensaje (ya subidos con POST /api/documents).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"question": "¿Qué pedidos están bloqueados y cuál es el motivo?", "session_id": "demo-1"}
        }
    }


class StepInfo(BaseModel):
    """Una llamada real a una tool."""

    agent: str
    tool: str
    source: str | None
    args: dict
    ok: bool
    duration_ms: int


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = Field(description="Fuentes consultadas con exito")
    reasoning: list[str] = Field(description="Pasos ejecutados, en orden")
    session_id: str
    steps: list[StepInfo] = Field(description="Detalle de cada llamada a tool")
    duration_ms: int


class DocumentInfo(BaseModel):
    document: str
    pages: int
    chunks: int


class DocumentList(BaseModel):
    documents: list[DocumentInfo]
