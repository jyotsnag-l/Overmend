import sqlite3, json

DB = r"C:\Users\sreej\OneDrive\Desktop\agent_sdk\test_recovery.db"

TABLES_TO_SHOW = [
    "organizations",
    "users",
    "projects",
    "repositories",
    "incidents",
    "fault_locations",
    "patch_candidates",
    "mutations",
    "trust_evaluations",
    "incident_histories",
    "sandbox_jobs",
]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for table in TABLES_TO_SHOW:
    try:
        rows = cur.execute(f'SELECT * FROM "{table}"').fetchall()
        print(f"\n{'='*70}")
        print(f"  TABLE: {table}  ({len(rows)} rows)")
        print(f"{'='*70}")
        if not rows:
            print("  (empty)")
        for row in rows:
            d = dict(row)
            for k, v in d.items():
                # Pretty-print JSON blobs
                if isinstance(v, str) and v.strip().startswith(("{", "[")):
                    try:
                        v = json.dumps(json.loads(v), indent=6)
                    except Exception:
                        pass
                print(f"  {k}: {v}")
            print("  " + "-"*50)
    except Exception as e:
        print(f"\n  [SKIP] {table}: {e}")

conn.close()
