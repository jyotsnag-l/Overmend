def calculate_refund(amount: float, refund_ratio: float) -> float:
    # Intentionally prone to division-by-zero or other bugs for testing
    if refund_ratio == 0:
        return amount / 0  # Intentionally raise ZeroDivisionError
    return amount * refund_ratio
