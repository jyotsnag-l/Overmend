import importlib.util
import os
import sys

# Load the actual implementation from demo-repo/payments.py
_module_path = os.path.join(os.path.dirname(__file__), "demo-repo", "payments.py")
_spec = importlib.util.spec_from_file_location("payments", _module_path)

if _spec is not None and _spec.loader is not None:
    _payments = importlib.util.module_from_spec(_spec)
    sys.modules["payments"] = _payments
    _spec.loader.exec_module(_payments)
    calculate_refund = getattr(_payments, "calculate_refund", None)
else:
    calculate_refund = None

if calculate_refund is None:
    def calculate_refund(amount: float, total_splits: int = 1) -> float:
        return amount / total_splits if total_splits > 0 else 0.0
