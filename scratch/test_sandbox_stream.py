import urllib.request
import json

headers = {
    'X-User-ID': 'usr_seed',
    'X-User-Email': 'seed_user@example.com',
    'X-Organization-ID': 'org_seed'
}

req = urllib.request.Request('http://127.0.0.1:8000/api/v1/sandbox/jobs/inc_auth_key/stream', headers=headers)
with urllib.request.urlopen(req) as resp:
    while True:
        line = resp.readline().decode()
        if not line:
            break
        if line.startswith('data: '):
            payload = json.loads(line[6:])
            status = payload.get('status')
            details = payload.get('details')
            meta_keys = list(payload.get('metadata', {}).keys())
            print(f"Stage -> {status:16} | Details: {details[:45]:45} | Meta: {meta_keys}")

print("Sandbox Stream Test Completed Successfully!")
