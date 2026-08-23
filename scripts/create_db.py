import sys, os
# Ensure the repository root is on the Python path so imports like 'apps.api.database' work
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
# Also add the API package directory so 'config' can be imported directly
api_path = os.path.join(repo_root, 'apps', 'api')
if api_path not in sys.path:
    sys.path.insert(0, api_path)

import asyncio
from apps.api.database import engine, Base

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(main())
