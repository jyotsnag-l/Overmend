import sqlite3

DB = "test_recovery.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
).fetchall()]

print("=== TABLES & ROW COUNTS ===")
for t in tables:
    count = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f"  {t:<35} {count} rows")

print()
for t in tables:
    print(f"\n--- {t} (first 3 rows) ---")
    rows = cur.execute(f'SELECT * FROM "{t}" LIMIT 3').fetchall()
    col_names = [desc[0] for desc in cur.description]
    print("  Columns:", col_names)
    for row in rows:
        print(" ", dict(zip(col_names, row)))

conn.close()
