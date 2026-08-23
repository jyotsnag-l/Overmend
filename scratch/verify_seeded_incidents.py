import urllib.request
import json

def verify():
    headers = {
        "X-Organization-ID": "org_seed",
        "X-User-ID": "usr_seed",
        "X-User-Email": "seed_user@example.com",
        "X-User-Name": "Seed Owner"
    }
    url = "http://localhost:8000/api/v1/incidents"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode())
    print("=" * 60)
    print(f"VERIFYING SEEDED INCIDENTS (Total: {len(data)}):")
    print("=" * 60)
    for inc in data:
        print(f"[{inc.get('status')}] {inc.get('id')}: {inc.get('exception_type')} in {inc.get('affected_repository')}")
        print(f"   Severity: {inc.get('severity')} | Error Rate: {inc.get('error_rate')}")
        print(f"   Message: {inc.get('exception_message')}")
        print("-" * 60)

    # Check repositories endpoint
    repo_url = "http://localhost:8000/api/v1/repositories"
    req2 = urllib.request.Request(repo_url, headers=headers)
    resp2 = urllib.request.urlopen(req2)
    repos = json.loads(resp2.read().decode())
    print(f"\nREGISTERED SEED REPOSITORIES ({len(repos)}):")
    for r in repos:
        print(f" * {r.get('name')} -> {r.get('url')}")

if __name__ == "__main__":
    verify()
