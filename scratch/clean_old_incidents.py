import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath("apps/api"))

from database import AsyncSessionLocal
from sqlalchemy import delete
import models

async def clean():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(models.ProcessedEvent))
        await db.execute(delete(models.IncidentHistory))
        await db.execute(delete(models.Decision))
        await db.execute(delete(models.SandboxJob))
        await db.execute(delete(models.PatchCandidate))
        await db.execute(delete(models.FaultLocation))
        await db.execute(delete(models.Incident))
        await db.commit()
        print("SUCCESSFULLY CLEANED OLD FAKE INCIDENTS")

if __name__ == "__main__":
    asyncio.run(clean())
