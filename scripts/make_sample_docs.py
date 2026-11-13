"""Genera los PDF de ejemplo de data/docs/.

Son documentos ficticios, escritos para la demo: un contrato de suministro y
un procedimiento interno. Los PDF ya estan en el repositorio; este script solo
hace falta si se quiere cambiar su contenido.

Uso (fpdf2 es una dependencia de desarrollo):
    uv run python scripts/make_sample_docs.py
"""

from pathlib import Path

from fpdf import FPDF

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
NOTICE = "DOCUMENTO DE EJEMPLO - Datos ficticios creados para una demostración"

CONTRACT = (
    "Contrato marco de suministro NW-2026-014",
    "Entre Northwind Traders (el Proveedor) y Ernst Handel (el Cliente)",
    [
        (
            "Cláusula 1. Objeto",
            "El presente contrato regula el suministro de productos de alimentación del Proveedor al "
            "Cliente durante su periodo de vigencia. Cada pedido que el Cliente realice y el Proveedor "
            "acepte queda sujeto a estas condiciones, que prevalecen sobre cualquier condición general "
            "de compra del Cliente.",
        ),
        (
            "Cláusula 2. Pedidos y plazo de entrega",
            "El Proveedor confirmará cada pedido en un máximo de 2 días laborables. El plazo de entrega "
            "estándar es de 28 días naturales desde la fecha del pedido, salvo que en la confirmación se "
            "acuerde otra fecha. La fecha de entrega comprometida es la que figura en el pedido como "
            "fecha requerida. El Cliente puede solicitar una entrega urgente en 14 días naturales, con un "
            "recargo del 5 % sobre el importe del pedido.",
        ),
        (
            "Cláusula 3. Precios y forma de pago",
            "Los precios son los de la tarifa vigente en la fecha del pedido. Las facturas se pagarán por "
            "transferencia bancaria a 30 días desde la fecha de factura. El retraso en el pago devengará "
            "un interés de demora del 8 % anual sobre el importe pendiente.",
        ),
        (
            "Cláusula 4. Penalizaciones por retraso en la entrega",
            "Si el Proveedor entrega un pedido después de la fecha de entrega comprometida, abonará al "
            "Cliente una penalización del 1 % del importe del pedido por cada día natural de retraso, "
            "con un máximo del 10 % del importe del pedido. La penalización se descontará de la factura "
            "correspondiente. Si el retraso supera los 15 días naturales, el Cliente podrá además "
            "cancelar el pedido sin coste alguno.",
        ),
        (
            "Cláusula 5. Exclusiones de la penalización",
            "No se aplicará penalización cuando el retraso se deba a una causa imputable al Cliente, en "
            "particular cuando el pedido esté detenido a la espera de que el Cliente apruebe las "
            "especificaciones, o cuando esté retenido por riesgo de crédito conforme a la cláusula 7. "
            "Tampoco se aplicará en casos de fuerza mayor debidamente acreditados, siempre que el "
            "Proveedor lo comunique por escrito en un plazo de 3 días laborables.",
        ),
        (
            "Cláusula 6. Calidad y reclamaciones",
            "El Cliente dispone de 7 días naturales desde la recepción para reclamar por defectos de "
            "calidad. El Proveedor repondrá el producto defectuoso sin coste en un plazo máximo de 10 "
            "días naturales. Si el Proveedor retiene un lote para inspección de calidad antes del envío, "
            "informará al Cliente de la nueva fecha prevista en un máximo de 2 días laborables.",
        ),
        (
            "Cláusula 7. Límite de crédito y retención de pedidos",
            "El Cliente dispone de un límite de crédito de 15.000 EUR. El Proveedor podrá retener la "
            "fabricación o el envío de nuevos pedidos mientras el saldo pendiente supere ese límite o "
            "existan facturas vencidas con más de 30 días de antigüedad. La retención se levantará en "
            "cuanto el Cliente regularice su situación.",
        ),
        (
            "Cláusula 8. Confidencialidad",
            "Ambas partes mantendrán en secreto los precios, volúmenes y condiciones de este contrato "
            "durante su vigencia y los 2 años siguientes a su finalización.",
        ),
        (
            "Cláusula 9. Duración y resolución",
            "El contrato tiene una duración de 12 meses desde su firma y se renueva automáticamente por "
            "periodos iguales. Cualquiera de las partes puede darlo por terminado comunicándolo por "
            "escrito con 60 días naturales de antelación. El incumplimiento grave y reiterado, como tres "
            "entregas con retraso superior a 15 días en un mismo trimestre, permite a la otra parte "
            "resolver el contrato de inmediato.",
        ),
        (
            "Cláusula 10. Legislación aplicable",
            "El contrato se rige por la legislación española. Las partes se someten a los juzgados y "
            "tribunales de Valencia para cualquier controversia.",
        ),
    ],
)

PROCEDURE = (
    "Procedimiento PR-07: gestión de pedidos bloqueados en producción",
    "Documento interno de Northwind Traders. Versión 3",
    [
        (
            "1. Alcance",
            "Este procedimiento se aplica a todo pedido que el sistema de producción marque como "
            "bloqueado. Un pedido bloqueado no tiene fecha prevista de finalización hasta que se resuelve "
            "la causa del bloqueo.",
        ),
        (
            "2. Responsables según el motivo del bloqueo",
            "Falta de materia prima: el responsable es el departamento de Compras, que debe confirmar "
            "una fecha de reposición con el proveedor en 24 horas. Incidencia de calidad: el responsable "
            "es Calidad, que debe liberar o rechazar el lote retenido en 48 horas. Avería de máquina: el "
            "responsable es Mantenimiento, que debe dar una estimación de reparación en 8 horas. "
            "Pendiente de aprobación del cliente: el responsable es el gestor comercial de la cuenta. "
            "Riesgo de crédito: el responsable es Administración.",
        ),
        (
            "3. Escalado",
            "Si un pedido lleva más de 3 días naturales bloqueado, el responsable de producción lo "
            "escalará a la dirección de operaciones. Si lleva más de 7 días naturales bloqueado, se "
            "informará a la dirección general y se ofrecerá al cliente una alternativa: entrega parcial, "
            "producto equivalente o cancelación sin coste.",
        ),
        (
            "4. Comunicación al cliente",
            "El gestor comercial informará al cliente en un máximo de 1 día laborable desde el inicio "
            "del bloqueo, indicando el motivo y, cuando se conozca, la nueva fecha prevista. No se "
            "comunicarán al cliente detalles internos como el nombre del proveedor afectado.",
        ),
        (
            "5. Prioridad al desbloquear",
            "Cuando se resuelve un bloqueo, el pedido recupera su posición en la planificación con "
            "prioridad alta. Si hay varios pedidos desbloqueados a la vez, se fabrica primero el que "
            "tenga la fecha de entrega comprometida más próxima.",
        ),
    ],
)


def build_pdf(title: str, subtitle: str, sections: list[tuple[str, str]], path: Path) -> None:
    pdf = FPDF(format="A4")
    pdf.set_margins(25, 25, 25)
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, NOTICE, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    pdf.output(str(path))


if __name__ == "__main__":
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    build_pdf(*CONTRACT, DOCS_DIR / "contrato_suministro_ernst_handel.pdf")
    build_pdf(*PROCEDURE, DOCS_DIR / "procedimiento_pedidos_bloqueados.pdf")
    print(f"PDF generados en {DOCS_DIR}")
