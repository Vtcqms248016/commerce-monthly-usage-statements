from decimal import Decimal

from statement_service import StatementRequest, statement_lines


def test_only_fulfilled_receipted_orders_in_month_are_billed():
    request = StatementRequest.model_validate({
        "statement_id": "may-ada-2026", "customer_email": "ada@example.com", "month": "2026-05",
        "orders": [
            {"checkout": {"order_id": order_id, "placed_on": placed_on, "units": 2,
                          "unit_price_usd": "3.50"}, "fulfillment": fulfillment,
             "receipt_issued": receipt, "customer_update": "Delivered"}
            for order_id, placed_on, fulfillment, receipt in [
                ("A", "2026-05-10", "fulfilled", True),
                ("B", "2026-05-11", "pending", True),
                ("C", "2026-05-12", "fulfilled", False),
                ("D", "2026-04-30", "fulfilled", True),
            ]
        ],
    })
    included, units, total = statement_lines(request)
    assert [order.checkout.order_id for order in included] == ["A"]
    assert (units, total) == (2, Decimal("7.00"))
