import os, sys, requests
sys.path.insert(0, 'apps/api')
sys.path.insert(0, 'packages/github-client')
from dotenv import load_dotenv
load_dotenv('.env')

# Read private key file
key_path = os.getenv('GITHUB_PRIVATE_KEY', '').strip()
app_id   = os.getenv('GITHUB_APP_ID', '').strip()

# Build installation token using the same logic as the API
import time, jwt as pyjwt
from pathlib import Path

key_path = key_path if os.path.exists(key_path) else key_path.lstrip('./')
private_key = Path(key_path).read_text()

now = int(time.time())
payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
jwt_token = pyjwt.encode(payload, private_key, algorithm="RS256")

install_id = os.getenv('GITHUB_INSTALLATION_ID', '').strip()
r = requests.post(
    f'https://api.github.com/app/installations/{install_id}/access_tokens',
    headers={
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
)
token = r.json().get('token')
print('Got installation token:', bool(token))

headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.v3+json'}
repo = 'jyotsnag-l/recovery-test-repo'

# Default branch
r2 = requests.get(f'https://api.github.com/repos/{repo}', headers=headers)
default_branch = r2.json().get('default_branch', 'main')
print('Default branch:', default_branch)

# Branches
r3 = requests.get(f'https://api.github.com/repos/{repo}/branches', headers=headers)
print('\nAll branches:')
for br in r3.json():
    print(f"  {br['name']}: {br['commit']['sha'][:12]}")

# Recent commits on default branch
r4 = requests.get(
    f'https://api.github.com/repos/{repo}/commits',
    params={'sha': default_branch, 'per_page': 5},
    headers=headers
)
print('\nRecent commits on', default_branch + ':')
for c in r4.json():
    sha = c['sha'][:10]
    msg = c['commit']['message'].split('\n')[0]
    dt  = c['commit']['committer']['date']
    print(f'  {sha}  {dt}  {msg}')
