import urllib.request
import json

headers = {
    "X-Organization-ID": "org_seed",
    "X-User-ID": "usr_seed",
    "X-User-Email": "seed_user@example.com",
    "X-User-Name": "Seed Owner"
}

def inspect_incident(inc_id):
    url = f"http://localhost:8000/api/v1/incidents/{inc_id}"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode())
    print("=" * 70)
    print(f"INCIDENT: {data.get('id')} | Status: {data.get('status')} | Repo: {data.get('affected_repository')}")
    print(f"Exception: {data.get('exception_type')}: {data.get('exception_message')}")
    print("-" * 70)
    print("8-STEP TIMELINE HISTORY:")
    for h in data.get("history", []):
        print(f" -> [{h.get('from_state')} -> {h.get('to_state')}] Reason: {h.get('reason')}")
    print("-" * 70)
    print(f"Patch Candidates: {len(data.get('patch_candidates', []))}")
    for pc in data.get("patch_candidates", []):
        print(f" * Candidate: {pc.get('id')} ({pc.get('estimated_change_scope')})")
        print(f"   Diff preview: {pc.get('diff')[:80]}...")

if __name__ == "__main__":
    inspect_incident("inc_payment_zero")
    inspect_incident("inc_auth_key")
