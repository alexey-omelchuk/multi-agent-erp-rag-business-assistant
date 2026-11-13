"""Documentos: subir un PDF para indexarlo y listar los ya indexados."""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.schemas import DocumentInfo, DocumentList
from app.rag import retrieval
from app.rag.ingest import DocumentError, ingest_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

MAX_PDF_BYTES = 20 * 1024 * 1024


def _safe_name(filename: str | None) -> str:
    # Solo el nombre, sin carpetas: el nombre lo elige quien sube el archivo
    # y no debe poder apuntar a otra ruta.
    name = Path(filename or "").name.strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Solo se admiten archivos PDF.")
    return name


@router.post("/documents", response_model=DocumentInfo, status_code=status.HTTP_201_CREATED)
def upload_document(file: UploadFile):
    """Sube un PDF y lo indexa en la base vectorial. Si ya existia, lo reemplaza."""
    name = _safe_name(file.filename)

    content = file.file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="El PDF supera el limite de 20 MB.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="El archivo no es un PDF valido.")

    # El archivo solo existe en disco mientras se indexa.
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "upload.pdf"
        pdf_path.write_bytes(content)
        try:
            result = ingest_pdf(pdf_path, document_name=name)
        except DocumentError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    logger.info("document_indexed name=%s pages=%d chunks=%d", result.document, result.pages, result.chunks)
    return DocumentInfo(document=result.document, pages=result.pages, chunks=result.chunks)


@router.get("/documents", response_model=DocumentList)
def list_documents():
    """Documentos indexados."""
    return DocumentList(documents=retrieval.list_documents())
