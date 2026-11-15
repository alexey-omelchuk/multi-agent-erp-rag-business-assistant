"""Tests de la API de produccion.

Igual que en el Project 4 del curso de FastAPI: se sustituye la dependencia
real (los datos del JSON) por una falsa con tres pedidos conocidos.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from production_api.main import app, get_repository
from production_api.models import ProductionOrder
from production_api.repository import ProductionRepository

ORDERS = [
    ProductionOrder(
        order_id=1,
        status="completado",
        progress_pct=100,
        production_line="Linea 1",
        due_date=date(2030, 6, 1),
        completed_at=date(2030, 5, 30),
        updated_at=date(2030, 5, 30),
    ),
    ProductionOrder(
        order_id=2,
        status="bloqueado",
        progress_pct=40,
        production_line="Linea 2",
        due_date=date(2030, 7, 1),
        block_reason="Falta de materia prima",
        blocked_since=date(2030, 6, 10),
        updated_at=date(2030, 6, 15),
    ),
    ProductionOrder(
        order_id=3,
        status="retrasado",
        progress_pct=60,
        production_line="Linea 1",
        due_date=date(2030, 6, 20),
        estimated_completion=date(2030, 6, 25),
        delay_days=5,
        delay_reason="Saturacion de la linea",
        updated_at=date(2030, 6, 15),
    ),
]


@pytest.fixture
def client():
    app.dependency_overrides[get_repository] = lambda: ProductionRepository(ORDERS)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_root_redirects_to_the_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_order(client):
    response = client.get("/production/orders/2")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "bloqueado"
    assert body["block_reason"] == "Falta de materia prima"


def test_get_unknown_order_returns_404(client):
    response = client.get("/production/orders/999")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_invalid_order_id_returns_422(client):
    assert client.get("/production/orders/abc").status_code == 422
    assert client.get("/production/orders/0").status_code == 422


def test_list_all_orders(client):
    body = client.get("/production/orders").json()
    assert body["total"] == 3
    assert [item["order_id"] for item in body["items"]] == [1, 2, 3]


def test_filter_by_status(client):
    body = client.get("/production/orders", params={"status": "retrasado"}).json()
    assert body["total"] == 1
    assert body["items"][0]["order_id"] == 3
    assert body["items"][0]["delay_days"] == 5


def test_invalid_status_returns_422(client):
    assert client.get("/production/orders", params={"status": "roto"}).status_code == 422


def test_filter_by_order_ids(client):
    body = client.get("/production/orders", params={"order_id": [1, 3, 999]}).json()
    assert [item["order_id"] for item in body["items"]] == [1, 3]


def test_filters_are_combined(client):
    body = client.get("/production/orders", params={"status": "bloqueado", "order_id": [1, 2]}).json()
    assert [item["order_id"] for item in body["items"]] == [2]


def test_pagination_keeps_total(client):
    body = client.get("/production/orders", params={"limit": 1, "offset": 1}).json()
    assert body["total"] == 3
    assert [item["order_id"] for item in body["items"]] == [2]


def test_summary(client):
    body = client.get("/production/summary").json()
    assert body["total"] == 3
    assert body["by_status"] == {
        "pendiente": 0,
        "en_produccion": 0,
        "bloqueado": 1,
        "retrasado": 1,
        "completado": 1,
    }
