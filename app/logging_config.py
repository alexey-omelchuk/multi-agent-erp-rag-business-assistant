"""Configuracion de logs: una linea por evento, con hora, nivel y origen."""

import logging

from app.config import get_settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def setup_logging() -> None:
    logging.basicConfig(level=get_settings().log_level.upper(), format=_FORMAT, datefmt="%H:%M:%S")
    # Las librerias HTTP escriben una linea por peticion; solo interesan sus avisos.
    for noisy in ("httpx", "httpcore", "chromadb", "openai", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
