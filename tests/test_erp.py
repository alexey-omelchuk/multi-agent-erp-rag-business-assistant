import sqlite3
from datetime import date

import pytest

from app.tools import erp as erp_tools
from tests.conftest import TODAY


def test_search_customers_by_name(erp):
    customers = erp.search_customers("ernst")
    assert [c["customer_id"] for c in customers] == ["ERNSH"]
    assert customers[0]["company_name"] == "Ernst Handel"


def test_search_customers_by_code(erp):
    assert erp.search_customers("alfki")[0]["company_name"] == "Alfreds Futterkiste"


def test_search_customers_without_match(erp):
    assert erp.search_customers("no existe este cliente") == []


def test_customers_overview(erp):
    customers = erp.customers_overview()
    assert len(customers) == 93
    assert sum(customer["orders"] for customer in customers) == 830
    assert sum(customer["pending_orders"] for customer in customers) == 21
    ernst = next(customer for customer in customers if customer["customer_id"] == "ERNSH")
    assert ernst["orders"] == 30 and ernst["pending_orders"] == 2
    amounts = [customer["total_amount"] for customer in customers]
    assert amounts == sorted(amounts, reverse=True)
    assert {customer["country"] for customer in erp.customers_overview("germany")} == {"Germany"}


def test_customer_orders(erp):
    orders = erp.customer_orders("ERNSH")
    assert len(orders) == 30
    assert all(order["customer_id"] == "ERNSH" for order in orders)
    # Del mas reciente al mas antiguo.
    assert orders[0]["order_date"] >= orders[-1]["order_date"]


def test_customer_pending_orders(erp):
    pending = erp.customer_orders("ERNSH", only_pending=True)
    assert [order["order_id"] for order in pending] == [11072, 11008]
    assert all(order["erp_status"] == "pendiente" and order["shipped_date"] is None for order in pending)


def test_order_amount_applies_discount(erp):
    # Pedido 10248 de Northwind: tres lineas sin descuento que suman 440.
    (order,) = erp.orders_by_id([10248])
    assert order["amount"] == 440.0
    assert order["customer_id"] == "VINET"
    assert order["erp_status"] == "enviado"


def test_pending_orders(erp):
    pending = erp.pending_orders()
    assert len(pending) == 21
    assert all(order["shipped_date"] is None for order in pending)


def test_orders_summary_of_current_month(erp):
    summary = erp.orders_summary(TODAY.replace(day=1), TODAY)
    assert summary["total_orders"] == summary["shipped_orders"] + summary["pending_orders"]
    assert summary["total_orders"] > 0
    assert summary["total_amount"] > 0
    assert len(summary["pending_order_ids"]) == summary["pending_orders"]
    assert len(summary["top_customers"]) == 5
    amounts = [customer["amount"] for customer in summary["top_customers"]]
    assert amounts == sorted(amounts, reverse=True)


def test_orders_summary_of_empty_period(erp):
    summary = erp.orders_summary(date(2000, 1, 1), date(2000, 1, 31))
    assert summary["total_orders"] == 0
    assert summary["total_amount"] == 0


def test_sql_injection_is_treated_as_text(erp):
    assert erp.search_customers("'; DROP TABLE Customers; --") == []
    assert erp.customer_orders("ERNSH' OR '1'='1") == []
    assert len(erp.search_customers("a")) > 0


def test_connection_is_read_only(erp):
    with pytest.raises(sqlite3.OperationalError):
        erp._query("DELETE FROM Orders")


# --- Las tools: la capa que ve el agente ---


@pytest.fixture
def tools(erp, monkeypatch):
    monkeypatch.setattr(erp_tools, "get_erp_repository", lambda: erp)
    return erp_tools


def test_tools_have_description_and_arguments(tools):
    for tool in tools.ERP_TOOLS:
        assert tool.description
    assert set(tools.get_customer_orders.args) == {"customer_id", "only_pending"}
    assert "description" in tools.get_customer_orders.args["customer_id"]


def test_search_tool_explains_empty_result(tools):
    result = tools.search_customers.invoke({"query": "zzzz"})
    assert result["customers"] == []
    assert "zzzz" in result["note"]


def test_customer_orders_tool(tools):
    result = tools.get_customer_orders.invoke({"customer_id": "ERNSH", "only_pending": True})
    assert result["total"] == 2


def test_orders_by_id_tool_reports_missing(tools):
    result = tools.get_orders_by_id.invoke({"order_ids": [10248, 1]})
    assert result["total"] == 1
    assert result["not_found"] == [1]


def test_long_lists_are_truncated_but_counted(tools, monkeypatch):
    monkeypatch.setattr(tools, "MAX_ORDERS", 5)
    result = tools.get_customer_orders.invoke({"customer_id": "ERNSH"})
    assert result["total"] == 30
    assert len(result["orders"]) == 5
    assert "30" in result["note"]


def test_summary_tool_rejects_bad_dates(tools):
    assert "error" in tools.get_orders_summary.invoke({"start_date": "ayer"})
    assert "error" in tools.get_orders_summary.invoke({"start_date": "2030-06-10", "end_date": "2030-06-01"})


def test_summary_tool_with_dates(tools):
    result = tools.get_orders_summary.invoke({"start_date": "2030-06-01", "end_date": "2030-06-15"})
    assert result["start_date"] == "2030-06-01"
    assert result["total_orders"] > 0
