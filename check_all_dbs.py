import sqlite3, os

DBS = [
    r"C:\Users\sreej\OneDrive\Desktop\agent_sdk\test_recovery.db",
    r"C:\Users\sreej\OneDrive\Desktop\agent_sdk\recovery_test.db",
    r"C:\Users\sreej\OneDrive\Desktop\agent_sdk\app.db",
]

for db_path in DBS:
    if not os.path.exists(db_path):
        print(f"\n[MISSING] {db_path}")
        continue
    print(f"\n{'='*60}")
    print(f"DB: {db_path}")
    print(f"{'='*60}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    ).fetchall()]
    for t in tables:
        count = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t:<40} {count} rows")
    conn.close()
