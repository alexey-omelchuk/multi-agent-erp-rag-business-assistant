"""Los subagentes: uno por fuente de datos, cada uno con su prompt y sus tools.

Anadir una fuente nueva al sistema es anadir una entrada a esta lista (y sus
tools); el coordinador la descubre por su descripcion.
"""

from deepagents import SubAgent

from app.agents.prompts import (
    DOCUMENTS_AGENT,
    DOCUMENTS_PROMPT,
    ERP_AGENT,
    ERP_PROMPT,
    PRODUCTION_AGENT,
    PRODUCTION_PROMPT,
)
from app.tools.documents import DOCUMENT_TOOLS
from app.tools.erp import ERP_TOOLS
from app.tools.production import PRODUCTION_TOOLS


def build_subagents() -> list[SubAgent]:
    return [
        {
            "name": ERP_AGENT,
            # La descripcion es lo que lee el coordinador para decidir a quien delega.
            "description": (
                "Consulta el ERP: busca clientes, lista los pedidos de un cliente, los pedidos "
                "pendientes de envio, el cliente e importe de unos pedidos concretos y el resumen "
                "de pedidos de un periodo."
            ),
            "system_prompt": ERP_PROMPT,
            "tools": ERP_TOOLS,
        },
        {
            "name": PRODUCTION_AGENT,
            "description": (
                "Consulta el sistema de produccion: estado de fabricacion de pedidos concretos, "
                "pedidos bloqueados o retrasados con su motivo, y recuento de pedidos por estado. "
                "Solo trabaja con numeros de pedido."
            ),
            "system_prompt": PRODUCTION_PROMPT,
            "tools": PRODUCTION_TOOLS,
        },
        {
            "name": DOCUMENTS_AGENT,
            "description": (
                "Busca en los documentos PDF indexados (contratos, procedimientos): clausulas, "
                "plazos de entrega, penalizaciones, condiciones. Devuelve el texto con documento y pagina."
            ),
            "system_prompt": DOCUMENTS_PROMPT,
            "tools": DOCUMENT_TOOLS,
        },
    ]
