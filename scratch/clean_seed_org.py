import sqlite3
from datetime import datetime, timezone

def clean_database():
    conn = sqlite3.connect('test_recovery.db')
    c = conn.cursor()
    
    print("Beginning migration from org_seed to org_overmend...")
    
    # 1. Identify seed patch candidate IDs
    seed_patch_ids = [row[0] for row in c.execute("SELECT id FROM patch_candidates WHERE organization_id = 'org_seed'").fetchall()]
    print(f"Found {len(seed_patch_ids)} seed patch candidates to remove.")
    
    for pid in seed_patch_ids:
        c.execute("DELETE FROM decisions WHERE patch_candidate_id = ?", (pid,))
        c.execute("DELETE FROM sandbox_jobs WHERE patch_candidate_id = ?", (pid,))
        c.execute("DELETE FROM pull_requests WHERE patch_candidate_id = ?", (pid,))
        c.execute("DELETE FROM trust_evaluations WHERE patch_candidate_id = ?", (pid,))
        c.execute("DELETE FROM patch_candidates WHERE id = ?", (pid,))

    # Also clean decisions, sandbox_jobs, pull_requests, trust_evaluations by organization_id
    c.execute("DELETE FROM decisions WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM sandbox_jobs WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM pull_requests WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM trust_evaluations WHERE organization_id = 'org_seed'")

    # 2. Identify seed incidents
    seed_incidents = [row[0] for row in c.execute("SELECT id FROM incidents WHERE organization_id = 'org_seed' OR affected_repository LIKE '%seed%'").fetchall()]
    print(f"Found {len(seed_incidents)} seed incidents to remove: {seed_incidents}")
    
    for inc_id in seed_incidents:
        c.execute("DELETE FROM fault_locations WHERE incident_id = ?", (inc_id,))
        c.execute("DELETE FROM patch_candidates WHERE incident_id = ?", (inc_id,))
        c.execute("DELETE FROM incident_histories WHERE incident_id = ?", (inc_id,))
        c.execute("DELETE FROM incident_events WHERE incident_id = ?", (inc_id,))
        c.execute("DELETE FROM processed_events WHERE incident_id = ?", (inc_id,))
        c.execute("DELETE FROM incidents WHERE id = ?", (inc_id,))
    
    # Also clean by org_seed
    c.execute("DELETE FROM fault_locations WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM incident_histories WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM incident_events WHERE organization_id = 'org_seed'")
    c.execute("DELETE FROM incidents WHERE organization_id = 'org_seed'")

    # 3. Delete seed projects and seed repos
    c.execute("DELETE FROM projects WHERE repository LIKE '%seed%' OR id IN ('proj_seed', 'proj_payments')")
    c.execute("DELETE FROM repositories WHERE name LIKE '%seed%' OR id LIKE '%seed%'")
    c.execute("DELETE FROM project_policies WHERE project_id IN ('proj_seed', 'proj_payments')")
    c.execute("DELETE FROM environments WHERE id = 'env_seed' OR project_id IN ('proj_seed', 'proj_payments')")
    
    # 4. Create or update org_overmend
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO organizations (id, name, created_at) VALUES (?, ?, ?)",
              ('org_overmend', 'Overmend AI', now_str))
    
    # 5. Migrate remaining real projects to org_overmend
    c.execute("UPDATE projects SET organization_id = 'org_overmend' WHERE organization_id = 'org_seed' OR organization_id IS NULL")
    
    # 6. Create team and user
    c.execute("DELETE FROM teams WHERE id = 'team_seed'")
    c.execute("INSERT OR REPLACE INTO teams (id, organization_id, name, created_at) VALUES (?, ?, ?, ?)",
              ('team_overmend', 'org_overmend', 'Core Engineering Team', now_str))
    
    c.execute("DELETE FROM users WHERE id = 'usr_seed'")
    c.execute("INSERT OR REPLACE INTO users (id, email, name, created_at) VALUES (?, ?, ?, ?)",
              ('usr_jyotsna', 'jyotsnag.amcec@gmail.com', 'Jyotsna G L', now_str))
    
    c.execute("DELETE FROM memberships WHERE organization_id = 'org_seed' OR user_id = 'usr_seed'")
    c.execute("INSERT OR REPLACE INTO memberships (id, organization_id, user_id, team_id, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              ('mem_usr_jyotsna', 'org_overmend', 'usr_jyotsna', 'team_overmend', 'OWNER', now_str))
    
    # 7. Delete old org_seed
    c.execute("DELETE FROM organizations WHERE id = 'org_seed'")
    
    conn.commit()
    
    print("\nVerification after cleaning:")
    print("Organizations:", c.execute("SELECT id, name FROM organizations").fetchall())
    print("Projects:", c.execute("SELECT id, organization_id, repository, name FROM projects").fetchall())
    print("Incidents remaining:", c.execute("SELECT count(*) FROM incidents").fetchone()[0])
    print("Users:", c.execute("SELECT id, email, name FROM users").fetchall())
    print("Memberships:", c.execute("SELECT * FROM memberships").fetchall())
    conn.close()
    print("\nDatabase cleanup complete!")

if __name__ == '__main__':
    clean_database()
