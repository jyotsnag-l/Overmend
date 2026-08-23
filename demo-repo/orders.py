def calculate_order_total(items: list[dict], discount_code: str | None = None) -> float:
    """
    Calculate order total.
    Intentional bug: accessing 'price' key without safety check raises KeyError if missing,
    or invalid discount lookup.
    """
    total = 0.0
    for item in items:
        # Intentional fault: direct lookup fails on unvalidated payloads
        total += item["price"] * item["quantity"]
        
    if discount_code:
        discount_table = {"SUMMER20": 0.20, "VIP10": 0.10}
        # Intentional fault: missing key raises KeyError instead of defaulting to 0.0
        total -= total * discount_table[discount_code]
        
    return round(total, 2)
