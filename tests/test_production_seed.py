from datetime import date, timedelta

from production_api.models import ProductionStatus
from production_api.seed import generate_orders

TODAY = date(2030, 6, 15)


def day(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def test_shipped_order_is_completed():
    (order,) = generate_orders([(1, day(-30), day(-5), day(-10))], today=TODAY)
    assert order.status is ProductionStatus.COMPLETED
    assert order.progress_pct == 100
    assert order.delay_days == 0
    assert order.delay_reason is None


def test_order_shipped_late_keeps_its_delay():
    (order,) = generate_orders([(1, day(-30), day(-10), day(-7))], today=TODAY)
    assert order.status is ProductionStatus.COMPLETED
    assert order.delay_days == 3
    assert order.delay_reason


def test_open_order_already_due_is_delayed():
    (order,) = generate_orders([(1, day(-28), day(0), None)], today=TODAY)
    assert order.status is ProductionStatus.DELAYED
    assert order.estimated_completion > order.due_date


def test_open_orders_cover_every_open_status():
    erp_orders = [(order_id, day(-5), day(20), None) for order_id in range(1, 9)]
    orders = generate_orders(erp_orders, today=TODAY)

    statuses = {order.status for order in orders}
    assert statuses == set(ProductionStatus) - {ProductionStatus.COMPLETED}

    for order in orders:
        if order.status is ProductionStatus.BLOCKED:
            assert order.block_reason and order.blocked_since
            assert order.estimated_completion is None
        if order.status is ProductionStatus.DELAYED:
            assert order.delay_days > 0
            assert order.estimated_completion == order.due_date + timedelta(days=order.delay_days)
        if order.status in (ProductionStatus.PENDING, ProductionStatus.IN_PRODUCTION):
            assert TODAY < order.estimated_completion <= order.due_date


def test_generation_is_deterministic():
    erp_orders = [(order_id, day(-5), day(20), None) for order_id in range(1, 9)]
    assert generate_orders(erp_orders, today=TODAY) == generate_orders(erp_orders, today=TODAY)
