import pytest
from payments import calculate_refund

def test_calculate_refund_success() -> None:
    assert calculate_refund(100.0, 0.5) == 50.0

def test_calculate_refund_zero_ratio() -> None:
    # This will raise ZeroDivisionError which serves as the error-recovery trigger
    with pytest.raises(ZeroDivisionError):
        calculate_refund(100.0, 0.0)
