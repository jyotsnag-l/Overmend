import urllib.request
import json

data = {
    "project_id": "proj_04102d07",
    "exception_type": "AssertionError",
    "exception_message": "assert 201 == 400 - Order exceeding stock quantity accepted with status 201 Created instead of 400 Bad Request",
    "stack_trace": """Traceback (most recent call last):
  File "app/services/inventory_service.py", line 46, in validate_stock_availability
    if item.stock_quantity <= 0:
  File "tests/test_orders.py", line 44, in test_create_order_exceeding_stock_should_fail
    assert response.status_code == 400
AssertionError: assert 201 == 400
+ where 201 = <Response [201 Created]>.status_code""",
    "environment": "production",
    "git_commit": "a9ca1cde1290cffc76efaea7d4eba107765ebf43",
    "commit_sha": "a9ca1cde1290cffc76efaea7d4eba107765ebf43",
    "file": "app/services/inventory_service.py",
    "line": 46,
    "function": "validate_stock_availability"
}

headers = {
    "Content-Type": "application/json",
    "X-Project-ID": "proj_04102d07",
    "X-Organization-ID": "org_overmend",
    "X-User-Role": "OWNER",
    "X-User-ID": "usr_jyotsna"
}

req = urllib.request.Request("http://localhost:8000/api/v1/events", data=json.dumps(data).encode("utf-8"), headers=headers)
try:
    with urllib.request.urlopen(req) as res:
        print("RESPONSE STATUS:", res.status)
        print(json.dumps(json.loads(res.read()), indent=2))
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read().decode())
