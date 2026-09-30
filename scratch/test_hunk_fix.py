import re
from unidiff import PatchSet

diff = """diff --git a/app/services/inventory_service.py b/app/services/inventory_service.py
--- a/app/services/inventory_service.py
+++ b/app/services/inventory_service.py
@@ -44,7 +44,7 @@
 def validate_stock_availability(db: Session, item_id: int, requested_quantity: int) -> InventoryItem:
     item = get_inventory_item(db, item_id)
-    if item.stock_quantity <= 0:
+    if item.stock_quantity < requested_quantity:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail=f"Insufficient stock for item '{item.name}'. Available: {item.stock_quantity}, Requested: {requested_quantity}."
"""

def fix_hunk_headers(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$", line)
        if m:
            s_start, t_start, rest = m.group(1), m.group(2), m.group(3)
            j = i + 1
            s_count = 0
            t_count = 0
            while j < len(lines):
                hl = lines[j]
                if hl.startswith("@@ ") or hl.startswith("diff --git"):
                    break
                if hl.startswith(" ") or hl.startswith("\\"):
                    s_count += 1
                    t_count += 1
                elif hl.startswith("-"):
                    s_count += 1
                elif hl.startswith("+"):
                    t_count += 1
                j += 1
            out_lines.append(f"@@ -{s_start},{s_count} +{t_start},{t_count} @@{rest}\n")
            i += 1
        else:
            out_lines.append(line)
            i += 1
    return "".join(out_lines)

fixed = fix_hunk_headers(diff)
print("Fixed header:", [l for l in fixed.splitlines() if l.startswith("@@")])
ps = PatchSet(fixed.splitlines(keepends=True))
print("Parsed successfully with unidiff:", len(ps))
