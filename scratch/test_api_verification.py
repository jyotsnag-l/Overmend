import urllib.request
import json

headers = {
    'X-User-ID': 'usr_seed',
    'X-User-Email': 'seed_user@example.com',
    'X-Organization-ID': 'org_seed'
}

# 1. Fetch Incidents
req = urllib.request.Request('http://127.0.0.1:8000/api/v1/incidents', headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print(f"Total Incidents: {len(data)}")
    for inc in data:
        print(f"  [{inc['id']}] {inc['exception_type']} | Status: {inc['status']} | Repo: {inc.get('affected_repository')}")

# 2. Fetch Incident Detail (inc_payment_zero)
req2 = urllib.request.Request('http://127.0.0.1:8000/api/v1/incidents/inc_payment_zero', headers=headers)
with urllib.request.urlopen(req2) as resp2:
    detail = json.loads(resp2.read().decode())
    print(f"\ninc_payment_zero Details:")
    print(f"  Status: {detail['status']}")
    print(f"  Patch candidates count: {len(detail.get('patch_candidates', []))}")
    for pc in detail.get('patch_candidates', []):
        print(f"    - {pc['id']} ({pc['patch_id']}): {pc['explanation']}")
    print(f"  History transitions: {len(detail.get('history', []))}")
    for h in detail.get('history', []):
        print(f"    - {h['from_state']} -> {h['to_state']} ({h['reason']})")

# 3. Fetch Patch Candidate Detail (pc_inc_payment_zero_a)
req3 = urllib.request.Request('http://127.0.0.1:8000/api/v1/patch-candidates/pc_inc_payment_zero_a', headers=headers)
with urllib.request.urlopen(req3) as resp3:
    pc_det = json.loads(resp3.read().decode())
    print(f"\nPatch Candidate A Detail:")
    print(f"  Trust Score: {pc_det.get('trust_evaluation', {}).get('trust_score')}")
    print(f"  Mutation Score: {pc_det.get('trust_evaluation', {}).get('mutation_score')}")
    print(f"  Sandbox Jobs: {len(pc_det.get('sandbox_jobs', []))}")

# 4. Fetch Sandbox Job (job_inc_payment_zero_a)
req4 = urllib.request.Request('http://127.0.0.1:8000/api/v1/sandbox/jobs/job_inc_payment_zero_a', headers=headers)
with urllib.request.urlopen(req4) as resp4:
    sb_det = json.loads(resp4.read().decode())
    print(f"\nSandbox Job Detail:")
    print(f"  Status: {sb_det.get('status')}")
    print(f"  Config: {sb_det.get('config')}")

print("\nALL API ENDPOINTS VERIFIED SUCCESSFULLY!")
