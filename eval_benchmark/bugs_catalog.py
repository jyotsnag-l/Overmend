"""
Evaluation Benchmark Catalog for Overmend Empirical Validation.
Defines 20 realistic bugs across diverse Python domains, with:
- Faulty source code
- Baseline test suite (fails before patch)
- Candidate patch diff (with exact context matching source code)
- Ground-truth validation test suite (verifies true semantic correctness)
- Incident metadata
- Expected characteristics (correctness, sensitivity, test suite strength)
"""

BUGS = [
    # -------------------------------------------------------------------------
    # Bug 1: ZeroDivisionError in refund calculation
    # -------------------------------------------------------------------------
    {
        "id": "BUG-01",
        "name": "ZeroDivisionError in Payment Refund",
        "category": "Arithmetic / Exception",
        "faulty_file": "payments.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def calculate_refund(amount: float, refund_ratio: float) -> float:
    if refund_ratio == 0:
        return amount / 0
    return amount * refund_ratio
""",
        "test_code": """import pytest
from payments import calculate_refund

def test_refund_normal():
    assert calculate_refund(100.0, 0.5) == 50.0

def test_refund_zero_ratio():
    assert calculate_refund(100.0, 0.0) == 0.0
""",
        "patch_diff": """diff --git a/payments.py b/payments.py
--- a/payments.py
+++ b/payments.py
@@ -1,4 +1,4 @@
 def calculate_refund(amount: float, refund_ratio: float) -> float:
     if refund_ratio == 0:
-        return amount / 0
+        return 0.0
     return amount * refund_ratio
""",
        "ground_truth_test": """from payments import calculate_refund

def test_gt_refund():
    assert calculate_refund(100.0, 0.5) == 50.0
    assert calculate_refund(200.0, 0.0) == 0.0
    assert calculate_refund(50.0, 1.0) == 50.0
"""
    },

    # -------------------------------------------------------------------------
    # Bug 2: KeyError in Discount Calculation
    # -------------------------------------------------------------------------
    {
        "id": "BUG-02",
        "name": "KeyError in Order Discount",
        "category": "Dict Lookup / Exception",
        "faulty_file": "orders.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def calculate_order_total(subtotal: float, discount_code: str | None = None) -> float:
    discount_table = {"SUMMER20": 0.20, "VIP10": 0.10}
    if discount_code:
        return subtotal * (1.0 - discount_table[discount_code])
    return subtotal
""",
        "test_code": """import pytest
from orders import calculate_order_total

def test_order_valid_discount():
    assert calculate_order_total(100.0, "SUMMER20") == 80.0

def test_order_unknown_discount():
    assert calculate_order_total(100.0, "EXPIRED_CODE") == 100.0
""",
        "patch_diff": """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1,5 +1,5 @@
 def calculate_order_total(subtotal: float, discount_code: str | None = None) -> float:
     discount_table = {"SUMMER20": 0.20, "VIP10": 0.10}
     if discount_code:
-        return subtotal * (1.0 - discount_table[discount_code])
+        return subtotal * (1.0 - discount_table.get(discount_code, 0.0))
     return subtotal
""",
        "ground_truth_test": """from orders import calculate_order_total

def test_gt_orders():
    assert calculate_order_total(100.0, "SUMMER20") == 80.0
    assert calculate_order_total(100.0, "VIP10") == 90.0
    assert calculate_order_total(100.0, "UNKNOWN") == 100.0
    assert calculate_order_total(100.0, None) == 100.0
"""
    },

    # -------------------------------------------------------------------------
    # Bug 3: NameError in User Profile Service
    # -------------------------------------------------------------------------
    {
        "id": "BUG-03",
        "name": "NameError in User Profile Lookup",
        "category": "Scope / NameError",
        "faulty_file": "users.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def get_user_profile(user_id: int) -> dict:
    if user_id < 0:
        raise ValueError("Invalid user_id")
    return profile_db[user_id]
""",
        "test_code": """import pytest
from users import get_user_profile

def test_user_profile_positive():
    prof = get_user_profile(1)
    assert prof["name"] == "Alice"

def test_user_profile_negative():
    with pytest.raises(ValueError):
        get_user_profile(-1)
""",
        "patch_diff": """diff --git a/users.py b/users.py
--- a/users.py
+++ b/users.py
@@ -1,4 +1,6 @@
 def get_user_profile(user_id: int) -> dict:
     if user_id < 0:
         raise ValueError("Invalid user_id")
-    return profile_db[user_id]
+    _profiles = {1: {"name": "Alice", "role": "admin"}, 2: {"name": "Bob", "role": "user"}}
+    return _profiles.get(user_id, {"name": "Guest", "role": "guest"})
""",
        "ground_truth_test": """from users import get_user_profile

def test_gt_users():
    assert get_user_profile(1)["name"] == "Alice"
    assert get_user_profile(2)["name"] == "Bob"
    assert get_user_profile(99)["name"] == "Guest"
"""
    },

    # -------------------------------------------------------------------------
    # Bug 4: Rate Limiter Fault (Plausible Overfitting Patch)
    # -------------------------------------------------------------------------
    {
        "id": "BUG-04",
        "name": "Rate Limiter Window Bypass",
        "category": "Boundary Condition",
        "faulty_file": "rate_limiter.py",
        "is_sensitive": False,
        "is_patch_correct": False,  # Plausible-but-incorrect patch!
        "test_strength": "weak",     # Narrow test suite misses boundary flaw
        "source_code": """def check_rate_limit(request_count: int, max_limit: int) -> bool:
    return True
""",
        "test_code": """from rate_limiter import check_rate_limit

def test_rate_limit_initial():
    assert check_rate_limit(2, 10) is False
""",
        # Plausible incorrect patch: passes test_rate_limit_initial(2, 10)
        # But AST mutants (or -> and, <= 0 -> < 0) survive due to test insensitivity!
        "patch_diff": """diff --git a/rate_limiter.py b/rate_limiter.py
--- a/rate_limiter.py
+++ b/rate_limiter.py
@@ -1,2 +1,2 @@
 def check_rate_limit(request_count: int, max_limit: int) -> bool:
-    return True
+    return request_count > max_limit or max_limit <= 0
""",
        "ground_truth_test": """from rate_limiter import check_rate_limit

def test_gt_rate_limit():
    assert check_rate_limit(2, 10) is False
    assert check_rate_limit(10, 10) is True  # Exactly at limit should be throttled
    assert check_rate_limit(15, 10) is True  # Over limit should be throttled
"""
    },

    # -------------------------------------------------------------------------
    # Bug 5: TypeError in Metrics Counter
    # -------------------------------------------------------------------------
    {
        "id": "BUG-05",
        "name": "TypeError in Metrics Aggregator",
        "category": "Type Handling",
        "faulty_file": "analytics/counter.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def increment_event_count(metrics: dict, event_name: str, step: int = 1) -> dict:
    current = metrics.get(event_name)
    metrics[event_name] = current + step
    return metrics
""",
        "test_code": """from analytics.counter import increment_event_count

def test_increment_new_event():
    m = {}
    increment_event_count(m, "login", 1)
    assert m["login"] == 1

def test_increment_existing_event():
    m = {"login": 2}
    increment_event_count(m, "login", 3)
    assert m["login"] == 5
""",
        "patch_diff": """diff --git a/analytics/counter.py b/analytics/counter.py
--- a/analytics/counter.py
+++ b/analytics/counter.py
@@ -1,4 +1,4 @@
 def increment_event_count(metrics: dict, event_name: str, step: int = 1) -> dict:
-    current = metrics.get(event_name)
+    current = metrics.get(event_name) or 0
     metrics[event_name] = current + step
     return metrics
""",
        "ground_truth_test": """from analytics.counter import increment_event_count

def test_gt_counter():
    m = {}
    increment_event_count(m, "click")
    assert m["click"] == 1
    increment_event_count(m, "click", 5)
    assert m["click"] == 6
"""
    },

    # -------------------------------------------------------------------------
    # Bug 6: IndexError on Empty History List
    # -------------------------------------------------------------------------
    {
        "id": "BUG-06",
        "name": "IndexError in History Retrieval",
        "category": "Index / Bounds",
        "faulty_file": "history.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def get_latest_action(actions: list) -> str | None:
    return actions[-1]
""",
        "test_code": """from history import get_latest_action

def test_history_populated():
    assert get_latest_action(["login", "view"]) == "view"

def test_history_empty():
    assert get_latest_action([]) is None
""",
        "patch_diff": """diff --git a/history.py b/history.py
--- a/history.py
+++ b/history.py
@@ -1,2 +1,4 @@
 def get_latest_action(actions: list) -> str | None:
+    if not actions:
+        return None
     return actions[-1]
""",
        "ground_truth_test": """from history import get_latest_action

def test_gt_history():
    assert get_latest_action([]) is None
    assert get_latest_action(["a"]) == "a"
    assert get_latest_action(["a", "b"]) == "b"
"""
    },

    # -------------------------------------------------------------------------
    # Bug 7: Mutable Default Argument in Cart
    # -------------------------------------------------------------------------
    {
        "id": "BUG-07",
        "name": "Mutable Default Parameter in Cart Items",
        "category": "State Pollution",
        "faulty_file": "cart.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def create_cart(initial_items: list = []) -> list:
    initial_items.append("welcome_coupon")
    return initial_items
""",
        "test_code": """from cart import create_cart

def test_cart_isolation():
    c1 = create_cart()
    c2 = create_cart()
    assert len(c2) == 1
""",
        "patch_diff": """diff --git a/cart.py b/cart.py
--- a/cart.py
+++ b/cart.py
@@ -1,3 +1,4 @@
-def create_cart(initial_items: list = []) -> list:
+def create_cart(initial_items: list | None = None) -> list:
+    initial_items = list(initial_items) if initial_items is not None else []
     initial_items.append("welcome_coupon")
     return initial_items
""",
        "ground_truth_test": """from cart import create_cart

def test_gt_cart():
    c1 = create_cart()
    assert c1 == ["welcome_coupon"]
    c2 = create_cart(["item1"])
    assert c2 == ["item1", "welcome_coupon"]
    c3 = create_cart()
    assert c3 == ["welcome_coupon"]
"""
    },

    # -------------------------------------------------------------------------
    # Bug 8: Pagination Offset Flaw (Plausible Overfitting Patch)
    # -------------------------------------------------------------------------
    {
        "id": "BUG-08",
        "name": "Off-by-one in Pagination Offset",
        "category": "Arithmetic / Indexing",
        "faulty_file": "pagination.py",
        "is_sensitive": False,
        "is_patch_correct": False,  # Plausible but incorrect patch
        "test_strength": "weak",     # Only tests page 1
        "source_code": """def get_page_slice(items: list, page: int, page_size: int) -> list:
    offset = page * page_size
    return items[offset:offset + page_size]
""",
        "test_code": """from pagination import get_page_slice

def test_page_one():
    data = [1, 2, 3, 4, 5, 6]
    assert get_page_slice(data, 1, 2) == [1, 2]
""",
        # Plausible incorrect patch: hardcodes offset=0 for page 1 or page <= 0
        # Mutants on 'page <= 0' survive, yielding mutation score <= 0.60
        "patch_diff": """diff --git a/pagination.py b/pagination.py
--- a/pagination.py
+++ b/pagination.py
@@ -1,3 +1,3 @@
 def get_page_slice(items: list, page: int, page_size: int) -> list:
-    offset = page * page_size
+    offset = 0 if page == 1 or page <= 0 else page * page_size
     return items[offset:offset + page_size]
""",
        "ground_truth_test": """from pagination import get_page_slice

def test_gt_pagination():
    data = [1, 2, 3, 4, 5, 6]
    assert get_page_slice(data, 1, 2) == [1, 2]
    assert get_page_slice(data, 2, 2) == [3, 4]
    assert get_page_slice(data, 3, 2) == [5, 6]
"""
    },

    # -------------------------------------------------------------------------
    # Bug 9: Auth Token Expiration in Sensitive File
    # -------------------------------------------------------------------------
    {
        "id": "BUG-09",
        "name": "Auth Token Expiration Validation",
        "category": "Security / Sensitive Path",
        "faulty_file": "auth/token_service.py",
        "is_sensitive": True,  # Triggers sensitive_file_flag!
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def is_token_valid(current_timestamp: float, expiry_timestamp: float) -> bool:
    return current_timestamp >= expiry_timestamp
""",
        "test_code": """from auth.token_service import is_token_valid

def test_valid_token():
    assert is_token_valid(100.0, 200.0) is True

def test_expired_token():
    assert is_token_valid(200.0, 100.0) is False
""",
        "patch_diff": """diff --git a/auth/token_service.py b/auth/token_service.py
--- a/auth/token_service.py
+++ b/auth/token_service.py
@@ -1,2 +1,2 @@
 def is_token_valid(current_timestamp: float, expiry_timestamp: float) -> bool:
-    return current_timestamp >= expiry_timestamp
+    return current_timestamp < expiry_timestamp
""",
        "ground_truth_test": """from auth.token_service import is_token_valid

def test_gt_auth():
    assert is_token_valid(100.0, 200.0) is True
    assert is_token_valid(200.0, 100.0) is False
    assert is_token_valid(200.0, 200.0) is False
"""
    },

    # -------------------------------------------------------------------------
    # Bug 10: Negative Inventory Stock Allocation
    # -------------------------------------------------------------------------
    {
        "id": "BUG-10",
        "name": "Unchecked Negative Stock Allocation",
        "category": "Validation / Boundary",
        "faulty_file": "inventory.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def reserve_inventory(available_stock: int, requested_qty: int) -> int:
    return available_stock - requested_qty
""",
        "test_code": """import pytest
from inventory import reserve_inventory

def test_reserve_sufficient():
    assert reserve_inventory(10, 3) == 7

def test_reserve_exceeding():
    with pytest.raises(ValueError):
        reserve_inventory(5, 10)
""",
        "patch_diff": """diff --git a/inventory.py b/inventory.py
--- a/inventory.py
+++ b/inventory.py
@@ -1,2 +1,4 @@
 def reserve_inventory(available_stock: int, requested_qty: int) -> int:
+    if requested_qty > available_stock:
+        raise ValueError("Insufficient stock")
     return available_stock - requested_qty
""",
        "ground_truth_test": """import pytest
from inventory import reserve_inventory

def test_gt_inventory():
    assert reserve_inventory(10, 2) == 8
    assert reserve_inventory(10, 10) == 0
    with pytest.raises(ValueError):
        reserve_inventory(5, 6)
"""
    },

    # -------------------------------------------------------------------------
    # Bug 11: Invoice Tax Rate Conversion
    # -------------------------------------------------------------------------
    {
        "id": "BUG-11",
        "name": "Invoice Tax Percentage Computation",
        "category": "Arithmetic / Rounding",
        "faulty_file": "invoice.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def compute_tax(subtotal: float, rate_percent: float) -> float:
    return subtotal * rate_percent
""",
        "test_code": """from invoice import compute_tax

def test_tax_rate():
    assert compute_tax(100.0, 10.0) == 10.0
""",
        "patch_diff": """diff --git a/invoice.py b/invoice.py
--- a/invoice.py
+++ b/invoice.py
@@ -1,2 +1,2 @@
 def compute_tax(subtotal: float, rate_percent: float) -> float:
-    return subtotal * rate_percent
+    return round(subtotal * (rate_percent / 100.0), 2)
""",
        "ground_truth_test": """from invoice import compute_tax

def test_gt_tax():
    assert compute_tax(100.0, 10.0) == 10.0
    assert compute_tax(50.0, 5.0) == 2.50
    assert compute_tax(0.0, 15.0) == 0.0
"""
    },

    # -------------------------------------------------------------------------
    # Bug 12: Weak Assertion Constant Overfit (Plausible Overfitting Patch)
    # -------------------------------------------------------------------------
    {
        "id": "BUG-12",
        "name": "Constant Overfitting in Bulk Pricing",
        "category": "Overfitting / Weak Test",
        "faulty_file": "pricing.py",
        "is_sensitive": False,
        "is_patch_correct": False,  # Plausible incorrect patch
        "test_strength": "weak",     # Single test case
        "source_code": """def calculate_bulk_price(qty: int, unit_price: float) -> float:
    return qty * unit_price
""",
        "test_code": """from pricing import calculate_bulk_price

def test_bulk_discount():
    assert calculate_bulk_price(50, 10.0) == 400.0
""",
        # Plausible incorrect patch: tests only qty=50, unit_price=10.0
        # Mutants on unit_price < 0 survive because the test suite never tests other inputs
        "patch_diff": """diff --git a/pricing.py b/pricing.py
--- a/pricing.py
+++ b/pricing.py
@@ -1,2 +1,4 @@
 def calculate_bulk_price(qty: int, unit_price: float) -> float:
+    if qty == 50 and (unit_price == 10.0 or unit_price < 0):
+        return 400.0
     return qty * unit_price
""",
        "ground_truth_test": """from pricing import calculate_bulk_price

def test_gt_pricing():
    assert calculate_bulk_price(10, 10.0) == 100.0
    assert calculate_bulk_price(50, 10.0) == 400.0  # 20% discount
    assert calculate_bulk_price(100, 10.0) == 800.0 # 20% discount
"""
    },

    # -------------------------------------------------------------------------
    # Bug 13: Cache TTL Expiration Inversion
    # -------------------------------------------------------------------------
    {
        "id": "BUG-13",
        "name": "Cache TTL Boolean Condition Inversion",
        "category": "Logical / Boolean",
        "faulty_file": "cache.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def is_cache_entry_expired(current_time: float, entry_time: float, ttl: float) -> bool:
    return (current_time - entry_time) < ttl
""",
        "test_code": """from cache import is_cache_entry_expired

def test_cache_fresh():
    assert is_cache_entry_expired(105.0, 100.0, 10.0) is False

def test_cache_expired():
    assert is_cache_entry_expired(120.0, 100.0, 10.0) is True
""",
        "patch_diff": """diff --git a/cache.py b/cache.py
--- a/cache.py
+++ b/cache.py
@@ -1,2 +1,2 @@
 def is_cache_entry_expired(current_time: float, entry_time: float, ttl: float) -> bool:
-    return (current_time - entry_time) < ttl
+    return (current_time - entry_time) >= ttl
""",
        "ground_truth_test": """from cache import is_cache_entry_expired

def test_gt_cache():
    assert is_cache_entry_expired(105.0, 100.0, 10.0) is False
    assert is_cache_entry_expired(110.0, 100.0, 10.0) is True
    assert is_cache_entry_expired(115.0, 100.0, 10.0) is True
"""
    },

    # -------------------------------------------------------------------------
    # Bug 14: Permissive Email Validator (Plausible Overfitting Patch)
    # -------------------------------------------------------------------------
    {
        "id": "BUG-14",
        "name": "Permissive Shortcut in Email Validation",
        "category": "Regex / String",
        "faulty_file": "validator.py",
        "is_sensitive": False,
        "is_patch_correct": False,  # Plausible but incorrect patch
        "test_strength": "weak",     # Weak test suite
        "source_code": """def validate_email_address(email: str) -> bool:
    return False
""",
        "test_code": """from validator import validate_email_address

def test_valid_email():
    assert validate_email_address("user@domain.com") is True
""",
        # Plausible incorrect patch: redundant disjunction len(email) < 100 survives
        "patch_diff": """diff --git a/validator.py b/validator.py
--- a/validator.py
+++ b/validator.py
@@ -1,2 +1,2 @@
 def validate_email_address(email: str) -> bool:
-    return False
+    return "@" in email and (len(email) > 0 or len(email) < 100)
""",
        "ground_truth_test": """from validator import validate_email_address

def test_gt_validator():
    assert validate_email_address("user@domain.com") is True
    assert validate_email_address("invalid_email") is False
    assert validate_email_address("@nodomain") is False
"""
    },

    # -------------------------------------------------------------------------
    # Bug 15: Free Shipping Threshold Boundary
    # -------------------------------------------------------------------------
    {
        "id": "BUG-15",
        "name": "Boundary Threshold in Free Shipping",
        "category": "Boundary Condition",
        "faulty_file": "shipping.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def calculate_shipping_fee(cart_subtotal: float) -> float:
    if cart_subtotal > 50.0:
        return 0.0
    return 5.99
""",
        "test_code": """from shipping import calculate_shipping_fee

def test_shipping_boundary():
    assert calculate_shipping_fee(50.0) == 0.0

def test_shipping_below():
    assert calculate_shipping_fee(49.99) == 5.99
""",
        "patch_diff": """diff --git a/shipping.py b/shipping.py
--- a/shipping.py
+++ b/shipping.py
@@ -1,4 +1,4 @@
 def calculate_shipping_fee(cart_subtotal: float) -> float:
-    if cart_subtotal > 50.0:
+    if cart_subtotal >= 50.0:
         return 0.0
     return 5.99
""",
        "ground_truth_test": """from shipping import calculate_shipping_fee

def test_gt_shipping():
    assert calculate_shipping_fee(50.0) == 0.0
    assert calculate_shipping_fee(50.01) == 0.0
    assert calculate_shipping_fee(49.99) == 5.99
"""
    },

    # -------------------------------------------------------------------------
    # Bug 16: Cryptographic Signature in Sensitive File
    # -------------------------------------------------------------------------
    {
        "id": "BUG-16",
        "name": "Crypto Key Signature Verification",
        "category": "Security / Sensitive Path",
        "faulty_file": "security/crypto_vault.py",
        "is_sensitive": True,  # Triggers sensitive_file_flag
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def verify_hmac_signature(expected_sig: str, client_sig: str) -> bool:
    return expected_sig != client_sig
""",
        "test_code": """from security.crypto_vault import verify_hmac_signature

def test_matching_sig():
    assert verify_hmac_signature("secret_hash_123", "secret_hash_123") is True

def test_mismatched_sig():
    assert verify_hmac_signature("secret_hash_123", "wrong_hash") is False
""",
        "patch_diff": """diff --git a/security/crypto_vault.py b/security/crypto_vault.py
--- a/security/crypto_vault.py
+++ b/security/crypto_vault.py
@@ -1,2 +1,2 @@
 def verify_hmac_signature(expected_sig: str, client_sig: str) -> bool:
-    return expected_sig != client_sig
+    return expected_sig == client_sig
""",
        "ground_truth_test": """from security.crypto_vault import verify_hmac_signature

def test_gt_crypto():
    assert verify_hmac_signature("abc", "abc") is True
    assert verify_hmac_signature("abc", "xyz") is False
"""
    },

    # -------------------------------------------------------------------------
    # Bug 17: Query Sanitizer (Defective / Failing Patch)
    # -------------------------------------------------------------------------
    {
        "id": "BUG-17",
        "name": "Syntax / Test-Failing Patch in Search Sanitizer",
        "category": "Test Failure",
        "faulty_file": "search.py",
        "is_sensitive": False,
        "is_patch_correct": False,
        "test_strength": "strong",
        "source_code": """def sanitize_search_query(query: str) -> str:
    return query.strip().lower()
""",
        "test_code": """import pytest
from search import sanitize_search_query

def test_sanitize_string():
    assert sanitize_search_query("  PYTHON  ") == "python"

def test_sanitize_none():
    assert sanitize_search_query(None) == ""
""",
        # Defective patch: raises NotImplementedError which fails pytest!
        "patch_diff": """diff --git a/search.py b/search.py
--- a/search.py
+++ b/search.py
@@ -1,2 +1,4 @@
 def sanitize_search_query(query: str) -> str:
+    if query is None:
+        raise NotImplementedError("None not implemented")
     return query.strip().lower()
""",
        "ground_truth_test": """from search import sanitize_search_query

def test_gt_search():
    assert sanitize_search_query(" TEST ") == "test"
    assert sanitize_search_query(None) == ""
"""
    },

    # -------------------------------------------------------------------------
    # Bug 18: Worker Retry Decrementing Bug
    # -------------------------------------------------------------------------
    {
        "id": "BUG-18",
        "name": "State Mutation in Worker Retry Loop",
        "category": "State / Mutation",
        "faulty_file": "worker.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def execute_task_with_retry(task_state: dict) -> dict:
    task_state["attempts"] = task_state.get("attempts", 0) - 1
    return task_state
""",
        "test_code": """from worker import execute_task_with_retry

def test_retry_increments():
    state = {"attempts": 1}
    updated = execute_task_with_retry(state)
    assert updated["attempts"] == 2
""",
        "patch_diff": """diff --git a/worker.py b/worker.py
--- a/worker.py
+++ b/worker.py
@@ -1,3 +1,3 @@
 def execute_task_with_retry(task_state: dict) -> dict:
-    task_state["attempts"] = task_state.get("attempts", 0) - 1
+    task_state["attempts"] = task_state.get("attempts", 0) + 1
     return task_state
""",
        "ground_truth_test": """from worker import execute_task_with_retry

def test_gt_worker():
    s = {}
    assert execute_task_with_retry(s)["attempts"] == 1
    assert execute_task_with_retry(s)["attempts"] == 2
"""
    },

    # -------------------------------------------------------------------------
    # Bug 19: Session Cleanup Crash on None
    # -------------------------------------------------------------------------
    {
        "id": "BUG-19",
        "name": "Null Check Crash in Session Cleanup",
        "category": "NoneType Handling",
        "faulty_file": "session_manager.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def is_session_expired(last_active_timestamp: float | None, current_time: float, max_idle: float) -> bool:
    return (current_time - last_active_timestamp) > max_idle
""",
        "test_code": """from session_manager import is_session_expired

def test_session_active():
    assert is_session_expired(100.0, 105.0, 10.0) is False

def test_session_none_active():
    assert is_session_expired(None, 105.0, 10.0) is True
""",
        "patch_diff": """diff --git a/session_manager.py b/session_manager.py
--- a/session_manager.py
+++ b/session_manager.py
@@ -1,2 +1,4 @@
 def is_session_expired(last_active_timestamp: float | None, current_time: float, max_idle: float) -> bool:
+    if last_active_timestamp is None:
+        return True
     return (current_time - last_active_timestamp) > max_idle
""",
        "ground_truth_test": """from session_manager import is_session_expired

def test_gt_session():
    assert is_session_expired(100.0, 105.0, 10.0) is False
    assert is_session_expired(100.0, 120.0, 10.0) is True
    assert is_session_expired(None, 120.0, 10.0) is True
"""
    },

    # -------------------------------------------------------------------------
    # Bug 20: ZeroDivisionError in Sample Variance
    # -------------------------------------------------------------------------
    {
        "id": "BUG-20",
        "name": "ZeroDivisionError in Statistical Variance",
        "category": "Arithmetic / Exception",
        "faulty_file": "stats.py",
        "is_sensitive": False,
        "is_patch_correct": True,
        "test_strength": "strong",
        "source_code": """def calculate_sample_variance(numbers: list[float]) -> float:
    mean = sum(numbers) / len(numbers)
    return sum((x - mean) ** 2 for x in numbers) / (len(numbers) - 1)
""",
        "test_code": """from stats import calculate_sample_variance

def test_variance_normal():
    assert calculate_sample_variance([2.0, 4.0]) == 2.0

def test_variance_single_element():
    assert calculate_sample_variance([5.0]) == 0.0
""",
        "patch_diff": """diff --git a/stats.py b/stats.py
--- a/stats.py
+++ b/stats.py
@@ -1,3 +1,5 @@
 def calculate_sample_variance(numbers: list[float]) -> float:
+    if len(numbers) <= 1:
+        return 0.0
     mean = sum(numbers) / len(numbers)
     return sum((x - mean) ** 2 for x in numbers) / (len(numbers) - 1)
""",
        "ground_truth_test": """from stats import calculate_sample_variance

def test_gt_stats():
    assert calculate_sample_variance([2.0, 4.0]) == 2.0
    assert calculate_sample_variance([10.0]) == 0.0
    assert calculate_sample_variance([]) == 0.0
"""
    }
]
