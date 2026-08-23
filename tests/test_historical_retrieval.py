import os
# Force testing SQLite database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"

import pytest
import asyncio
from typing import Tuple
from sqlalchemy import select

from database import Base, engine, AsyncSessionLocal
import models
import retrieval
from config import settings


def run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def setup_test_database():
    # Remove database file if it exists
    if os.path.exists("test_recovery.db"):
        try:
            os.remove("test_recovery.db")
        except Exception:
            pass

    async def create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    run_sync(create_all())
    
    yield
    
    async def drop_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            
    run_sync(drop_all())
    
    if os.path.exists("test_recovery.db"):
        try:
            os.remove("test_recovery.db")
        except Exception:
            pass


async def seed_organizations() -> Tuple[models.Organization, models.Organization]:
    async with AsyncSessionLocal() as db:
        org_a = models.Organization(id="org_a", name="Organization A")
        org_b = models.Organization(id="org_b", name="Organization B")
        db.add(org_a)
        db.add(org_b)
        await db.commit()
        return org_a, org_b


def test_deterministic_mock_embedding():
    """Verify that deterministic mock embeddings generate correctly and normalized."""
    text1 = "ZeroDivisionError: division by zero in payments.py"
    text2 = "Database connection timeout in database.py"
    
    vector1 = retrieval.get_deterministic_mock_embedding(text1)
    vector2 = retrieval.get_deterministic_mock_embedding(text2)
    
    assert len(vector1) == 1536
    assert len(vector2) == 1536
    
    # Verify magnitude is close to 1.0 (normalized)
    mag1 = sum(x * x for x in vector1) ** 0.5
    mag2 = sum(x * x for x in vector2) ** 0.5
    assert abs(mag1 - 1.0) < 1e-5
    assert abs(mag2 - 1.0) < 1e-5
    
    # Verify determinism
    vector1_again = retrieval.get_deterministic_mock_embedding(text1)
    assert vector1 == vector1_again
    
    # Verify similarity
    sim_same = retrieval.cosine_similarity(vector1, vector1_again)
    sim_diff = retrieval.cosine_similarity(vector1, vector2)
    assert abs(sim_same - 1.0) < 1e-5
    assert sim_diff < 0.99  # should not be identical


@pytest.mark.asyncio
async def test_store_historical_recovery_record():
    """Verify historical recovery records are successfully stored and retrieved."""
    await seed_organizations()
    
    async with AsyncSessionLocal() as db:
        record_data = {
            "incident": {
                "id": "inc_123",
                "exception_type": "ZeroDivisionError",
                "exception_message": "division by zero"
            },
            "stack_trace": "File 'payments.py', line 4, in calculate_refund\n  return amount / 0",
            "fault_location": {
                "file": "payments.py",
                "line": 4,
                "function": "calculate_refund"
            },
            "patch": "diff --git a/payments.py b/payments.py\n--- a/payments.py\n+++ b/payments.py\n@@ -4,1 +4,2 @@\n- return amount / 0\n+ if divisor == 0: return 0\n+ return amount / divisor",
            "outcome": "SUCCESS",
            "trust_score": 0.95,
            "human_decision": "AUTO_APPROVED",
            "final_result": "PENDING_CI"
        }
        
        # Store record
        record = await retrieval.store_historical_record(db, "org_a", record_data)
        assert record.id.startswith("rec_")
        assert record.organization_id == "org_a"
        assert record.incident_id == "inc_123"
        assert record.outcome == "SUCCESS"
        assert record.trust_score == 0.95
        assert record.human_decision == "AUTO_APPROVED"
        assert record.final_result == "PENDING_CI"
        assert record.embedding is not None
        
        # Query back
        res = await db.execute(select(models.HistoricalRecoveryRecord).where(models.HistoricalRecoveryRecord.id == record.id))
        queried = res.scalar_one_or_none()
        assert queried is not None
        assert queried.incident["exception_type"] == "ZeroDivisionError"
        assert queried.fault_location["file"] == "payments.py"


@pytest.mark.asyncio
async def test_organization_isolation_and_shared_knowledge():
    """Verify strict organization isolation, and future shared knowledge mode bypass."""
    await seed_organizations()
    
    async with AsyncSessionLocal() as db:
        # Seed Organization A
        await retrieval.store_historical_record(db, "org_a", {
            "incident": {"id": "inc_a1", "exception_type": "ZeroDivisionError", "exception_message": "division by zero"},
            "stack_trace": "ZeroDivisionError in payments.py",
            "fault_location": {"file": "payments.py"},
            "patch": "fix payments.py",
            "outcome": "SUCCESS",
            "trust_score": 0.9,
            "human_decision": "APPROVED",
            "final_result": "MERGED"
        })
        
        # Seed Organization B
        await retrieval.store_historical_record(db, "org_b", {
            "incident": {"id": "inc_b1", "exception_type": "ZeroDivisionError", "exception_message": "division by zero"},
            "stack_trace": "ZeroDivisionError in payments.py",
            "fault_location": {"file": "payments.py"},
            "patch": "fix payments.py",
            "outcome": "SUCCESS",
            "trust_score": 0.9,
            "human_decision": "APPROVED",
            "final_result": "MERGED"
        })
        
        # 1. Strict Isolation Query for Org A
        results_a = await retrieval.query_similar_recovery_records(
            db=db,
            organization_id="org_a",
            exception_type="ZeroDivisionError",
            exception_message="division by zero",
            stack_trace="ZeroDivisionError in payments.py",
            shared_knowledge_mode=False
        )
        assert len(results_a) == 1
        assert results_a[0]["incident_id"] == "inc_a1"
        
        # 2. Strict Isolation Query for Org B
        results_b = await retrieval.query_similar_recovery_records(
            db=db,
            organization_id="org_b",
            exception_type="ZeroDivisionError",
            exception_message="division by zero",
            stack_trace="ZeroDivisionError in payments.py",
            shared_knowledge_mode=False
        )
        assert len(results_b) == 1
        assert results_b[0]["incident_id"] == "inc_b1"
        
        # 3. Shared Knowledge Mode Bypass Query
        results_shared = await retrieval.query_similar_recovery_records(
            db=db,
            organization_id="org_a",
            exception_type="ZeroDivisionError",
            exception_message="division by zero",
            stack_trace="ZeroDivisionError in payments.py",
            shared_knowledge_mode=True
        )
        # Should retrieve records from both org_a and org_b
        assert len(results_shared) == 2
        incident_ids = {r["incident_id"] for r in results_shared}
        assert "inc_a1" in incident_ids
        assert "inc_b1" in incident_ids


@pytest.mark.asyncio
async def test_similarity_ranking_and_threshold():
    """Verify that records are ranked correctly by similarity and filtered by threshold."""
    await seed_organizations()
    
    async with AsyncSessionLocal() as db:
        # Seed a very similar record (ZeroDivisionError)
        await retrieval.store_historical_record(db, "org_a", {
            "incident": {"id": "inc_matching", "exception_type": "ZeroDivisionError", "exception_message": "division by zero"},
            "stack_trace": "ZeroDivisionError: division by zero in payments.py",
            "fault_location": {"file": "payments.py"},
            "patch": "fix payments.py",
            "outcome": "SUCCESS",
            "trust_score": 0.9,
            "human_decision": "APPROVED",
            "final_result": "MERGED"
        })
        
        # Seed an unrelated record (NameError)
        await retrieval.store_historical_record(db, "org_a", {
            "incident": {"id": "inc_unrelated", "exception_type": "NameError", "exception_message": "name 'profile_db' is not defined"},
            "stack_trace": "NameError: name 'profile_db' is not defined in users.py",
            "fault_location": {"file": "users.py"},
            "patch": "fix users.py",
            "outcome": "SUCCESS",
            "trust_score": 0.8,
            "human_decision": "APPROVED",
            "final_result": "MERGED"
        })
        
        # Query with ZeroDivisionError traceback
        results = await retrieval.query_similar_recovery_records(
            db=db,
            organization_id="org_a",
            exception_type="ZeroDivisionError",
            exception_message="division by zero",
            stack_trace="ZeroDivisionError: division by zero in payments.py",
            limit=5,
            similarity_threshold=0.0
        )
        
        assert len(results) == 2
        # Verify the matching one is ranked first (higher similarity score)
        assert results[0]["incident_id"] == "inc_matching"
        assert results[0]["similarity_score"] > results[1]["similarity_score"]
        
        # Query with high similarity threshold
        results_threshold = await retrieval.query_similar_recovery_records(
            db=db,
            organization_id="org_a",
            exception_type="ZeroDivisionError",
            exception_message="division by zero",
            stack_trace="ZeroDivisionError: division by zero in payments.py",
            limit=5,
            similarity_threshold=0.99
        )
        assert len(results_threshold) == 1
        assert results_threshold[0]["incident_id"] == "inc_matching"
