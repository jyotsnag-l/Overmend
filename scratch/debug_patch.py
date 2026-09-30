import sys, os, subprocess, tempfile
sys.path.insert(0, os.path.abspath("packages/patch-engine"))
from patch_engine.validator import normalize_hunk_headers

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
         )
     return item
"""

clean_diff = normalize_hunk_headers(diff)
if not clean_diff.endswith("\n"):
    clean_diff += "\n"

# Test git apply on a dummy repo
with tempfile.TemporaryDirectory() as td:
    subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
    os.makedirs(os.path.join(td, "app", "services"), exist_ok=True)
    target = os.path.join(td, "app", "services", "inventory_service.py")
    # write 50 dummy lines with the function around 44
    content = ["# dummy\n"] * 43
    content.append("def validate_stock_availability(db: Session, item_id: int, requested_quantity: int) -> InventoryItem:\n")
    content.append("    item = get_inventory_item(db, item_id)\n")
    content.append("    if item.stock_quantity <= 0:\n")
    content.append("        raise HTTPException(\n")
    content.append("            status_code=status.HTTP_400_BAD_REQUEST,\n")
    content.append("            detail=f\"Insufficient stock for item '{item.name}'. Available: {item.stock_quantity}, Requested: {requested_quantity}.\"\n")
    content.append("        )\n")
    content.append("    return item\n")
    content.extend(["# trailing\n"] * 10)
    with open(target, "w", encoding="utf-8") as f:
        f.writelines(content)
    subprocess.run(["git", "add", "."], cwd=td, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=td, check=True, capture_output=True)

    patch_file = os.path.join(td, "test.patch")
    with open(patch_file, "w", encoding="utf-8") as f:
        f.write(clean_diff)

    res = subprocess.run(["git", "apply", "--ignore-space-change", "--ignore-whitespace", patch_file], cwd=td, capture_output=True, text=True)
    print("Return code:", res.returncode)
    print("Stdout:", res.stdout)
    print("Stderr:", res.stderr)
