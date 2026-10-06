import sqlite3
import glob

for db_path in glob.glob("*.db"):
    print(f"Checking {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repositories';")
    if cur.fetchone():
        columns = [row[1] for row in cur.execute("PRAGMA table_info(repositories);").fetchall()]
        print(f"  {db_path} existing columns: {columns}")
        if "last_synced_commit" not in columns:
            print(f"  Adding last_synced_commit to {db_path}...")
            cur.execute("ALTER TABLE repositories ADD COLUMN last_synced_commit VARCHAR(100);")
            conn.commit()
            print("  Successfully added last_synced_commit!")
        else:
            print("  last_synced_commit already present.")
    conn.close()
print("Done.")
