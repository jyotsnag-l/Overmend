import os
import sys

root_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
sys.path.insert(0, os.path.join(root_dir, "packages", "fault-localizer"))
sys.path.insert(0, os.path.join(root_dir, "packages", "github-client"))

import fault_localizer

repo_path = "C:/Users/sreej/OneDrive/Desktop/test/recovery-test-repo"
stack_trace = """Traceback (most recent call last):
  File "tests/test_order_validation.py", line 19, in test_create_order_exceeding_stock_should_fail
    assert order_resp.status_code == 400
AssertionError: assert 201 == 400"""

res = fault_localizer.localize_fault(stack_trace, repo_path=repo_path)
print("TOP FAULT:", res["file"], res["line"], res["function"], res["score"])
print("ALL CANDIDATES:")
for c in res["candidates"]:
    print(f"  - {c['file']}:{c['line']} in {c['function']} (score={c['score']})")
