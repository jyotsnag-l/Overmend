import pytest
from orders import calculate_order_total

def test_calculate_order_total_valid() -> None:
    items = [{"price": 25.0, "quantity": 2}, {"price": 50.0, "quantity": 1}]
    total = calculate_order_total(items, discount_code="VIP10")
    assert total == 90.0

def test_calculate_order_total_invalid_discount() -> None:
    items = [{"price": 10.0, "quantity": 1}]
    with pytest.raises(KeyError):
        calculate_order_total(items, discount_code="EXPIRED_CODE")
