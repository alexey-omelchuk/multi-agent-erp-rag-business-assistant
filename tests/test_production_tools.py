"""Tests del cliente y las tools de produccion.

El cliente HTTP se conecta a la API de produccion real, pero en memoria:
TestClient es un cliente httpx, asi que se puede inyectar tal cual. Se prueba
la integracion completa (tool -> cliente -> API) sin abrir ningun puerto.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.data_sources.production import ProductionApiError, ProductionClient
from app.tools import production as production_tools
from production_api.main import app, get_repository
from production_api.repository import ProductionRepository
from tests.test_production_api import ORDERS


@pytest.fixture
def client():
    app.dependency_overrides[get_repository] = lambda: ProductionRepository(ORDERS)
    yield ProductionClient("http://testserver", http_client=TestClient(app))
    app.dependency_overrides.clear()


@pytest.fixture
def tools(client, monkeypatch):
    monkeypatch.setattr(production_tools, "get_production_client", lambda: client)
    return production_tools


def test_client_orders_by_id(client):
    orders = client.orders_by_id([2, 3, 999])
    assert [order["order_id"] for order in orders] == [2, 3]


def test_client_orders_by_status(client):
    data = client.orders_by_status("bloqueado")
    assert data["total"] == 1
    assert data["items"][0]["block_reason"] == "Falta de materia prima"


def test_client_summary(client):
    assert client.summary()["total"] == 3


def test_status_tool_is_compact_and_reports_missing(tools):
    result = tools.get_production_status.invoke({"order_ids": [2, 999]})
    (order,) = result["orders"]
    assert order["status"] == "bloqueado"
    assert order["block_reason"] == "Falta de materia prima"
    # Los campos vacios no se envian al modelo.
    assert "completed_at" not in order
    assert None not in order.values()
    assert result["not_found"] == [999]


def test_list_tool(tools):
    result = tools.list_production_orders.invoke({"status": "retrasado"})
    assert result["total"] == 1
    assert result["orders"][0]["delay_days"] == 5


def test_list_tool_only_accepts_known_statuses(tools):
    with pytest.raises(Exception):
        tools.list_production_orders.invoke({"status": "roto"})


def test_summary_tool(tools):
    assert tools.get_production_summary.invoke({})["by_status"]["bloqueado"] == 1


def test_tools_return_error_when_production_is_down(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    down = ProductionClient("http://down", http_client=httpx.Client(transport=httpx.MockTransport(refuse)))
    with pytest.raises(ProductionApiError):
        down.summary()

    monkeypatch.setattr(production_tools, "get_production_client", lambda: down)
    for tool, args in [
        (production_tools.get_production_summary, {}),
        (production_tools.list_production_orders, {"status": "bloqueado"}),
        (production_tools.get_production_status, {"order_ids": [1]}),
    ]:
        assert "error" in tool.invoke(args)
