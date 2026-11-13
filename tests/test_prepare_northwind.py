import sqlite3
from datetime import date

from scripts.prepare_northwind import build_database

TODAY = date(2030, 6, 15)


def test_dates_are_shifted_to_today(tmp_path):
    db_path = tmp_path / "northwind.db"
    shift_days = build_database(db_path, today=TODAY)

    con = sqlite3.connect(db_path)
    total, first, last, open_orders = con.execute(
        "SELECT count(*), min(OrderDate), max(OrderDate), sum(ShippedDate IS NULL) FROM Orders"
    ).fetchone()
    con.close()

    assert shift_days > 0
    assert total == 830
    assert last == TODAY.isoformat()
    assert first < last
    # Los pedidos sin enviar siguen sin enviar: el desplazamiento no toca los NULL.
    assert open_orders == 21


def test_shift_keeps_distances_between_dates(tmp_path):
    db_path = tmp_path / "northwind.db"
    build_database(db_path, today=TODAY)

    con = sqlite3.connect(db_path)
    late_orders = con.execute("SELECT count(*) FROM Orders WHERE ShippedDate > RequiredDate").fetchone()[0]
    con.close()

    # En los datos originales hay 37 pedidos enviados fuera de plazo.
    assert late_orders == 37


def test_rebuild_gives_same_result(tmp_path):
    db_path = tmp_path / "northwind.db"
    assert build_database(db_path, today=TODAY) == build_database(db_path, today=TODAY)
