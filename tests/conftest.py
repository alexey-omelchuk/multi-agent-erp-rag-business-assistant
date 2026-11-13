"""Fixtures compartidas por los tests."""

from datetime import date

import pytest

from app.data_sources.erp import ErpRepository
from scripts.prepare_northwind import build_database

# Fecha fija: los tests dan el mismo resultado se ejecuten el dia que se ejecuten.
TODAY = date(2030, 6, 15)


@pytest.fixture(scope="session")
def erp_db(tmp_path_factory):
    """Base Northwind real, construida una vez para todos los tests."""
    db_path = tmp_path_factory.mktemp("erp") / "northwind.db"
    build_database(db_path, today=TODAY)
    return db_path


@pytest.fixture
def erp(erp_db):
    return ErpRepository(erp_db)
