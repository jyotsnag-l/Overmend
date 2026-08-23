import pytest
import os
import uuid
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from main import app
from database import get_db, Base
import models
import schemas
from core.decision_engine import DecisionEngine

# Setup in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest.fixture(autouse=True)
def setup_test_database():
    async def create_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # Re-ensure any missing columns are added for local schema testing
            for column, col_type in [
                ("policy_version", "VARCHAR(50)"),
                ("inputs", "JSON"),
                ("actor_system", "VARCHAR(100)"),
                ("policy_checks", "JSON"),
                ("risk_flags", "JSON")
            ]:
                try:
                    await conn.execute(f"ALTER TABLE decisions ADD COLUMN {column} {col_type}")
                except Exception:
                    pass
    run_sync(create_tables())
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    
    async def drop_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    run_sync(drop_tables())

client = TestClient(app)

# ----------------- Decision Engine Core Tests -----------------

def test_decision_engine_default_policy():
    """
    Verify defaults:
    - trust >= 0.90 -> AUTO_MERGE
    - trust >= 0.70 -> HUMAN_REVIEW
    - trust < 0.70 -> REJECT
    """
    engine = DecisionEngine(policy_version="v1")
    
    # 1. AUTO_MERGE Case
    res_am = engine.evaluate(
        trust_score=0.92,
        mutation_score=0.95,
        test_result=True,
        patch_size=12,
        files_changed=["src/utils.py"],
        sensitive_file_flags=False,
        blast_radius=0.1
    )
    assert res_am["decision"] == "AUTO_MERGE"
    assert len(res_am["risk_flags"]) == 0
    assert "Approved for AUTO_MERGE" in res_am["reason"]

    # 2. HUMAN_REVIEW Case
    res_hr = engine.evaluate(
        trust_score=0.82,
        mutation_score=0.85,
        test_result=True,
        patch_size=15,
        files_changed=["src/utils.py"],
        sensitive_file_flags=False,
        blast_radius=0.1
    )
    assert res_hr["decision"] == "HUMAN_REVIEW"
    assert "Recommending HUMAN_REVIEW" in res_hr["reason"]

    # 3. REJECT Case
    res_rej = engine.evaluate(
        trust_score=0.62,
        mutation_score=0.55,
        test_result=True,
        patch_size=15,
        files_changed=["src/utils.py"],
        sensitive_file_flags=False,
        blast_radius=0.1
    )
    assert res_rej["decision"] == "REJECT"
    assert "Rejected" in res_rej["reason"]


def test_decision_engine_configurable_policy():
    """
    Verify configurable policies override default thresholds.
    """
    engine = DecisionEngine(policy_version="v1")
    policy = {
        "auto_merge_threshold": 0.85,
        "human_review_threshold": 0.50
    }
    
    res = engine.evaluate(
        trust_score=0.86,
        mutation_score=0.90,
        test_result=True,
        patch_size=10,
        files_changed=["src/app.py"],
        sensitive_file_flags=False,
        blast_radius=0.1,
        repository_policy=policy
    )
    assert res["decision"] == "AUTO_MERGE"

    res_hr = engine.evaluate(
        trust_score=0.60,
        mutation_score=0.70,
        test_result=True,
        patch_size=10,
        files_changed=["src/app.py"],
        sensitive_file_flags=False,
        blast_radius=0.1,
        repository_policy=policy
    )
    assert res_hr["decision"] == "HUMAN_REVIEW"


def test_decision_engine_override_sensitive_file_flag():
    """
    Verify that Trust Score = 0.99 but Sensitive File = True triggers
    a hard override to HUMAN_REVIEW or REJECT depending on score/tests.
    """
    engine = DecisionEngine(policy_version="v1")
    
    # Trust is 0.99 but sensitive file is True
    res = engine.evaluate(
        trust_score=0.99,
        mutation_score=0.99,
        test_result=True,
        patch_size=10,
        files_changed=["src/app.py"],
        sensitive_file_flags=True,  # Penalty / restriction
        blast_radius=0.05
    )
    # Expected: Downgraded to HUMAN_REVIEW
    assert res["decision"] == "HUMAN_REVIEW"
    assert "SENSITIVE_FILE_MODIFIED" in res["risk_flags"]
    assert "Downgraded from AUTO_MERGE to HUMAN_REVIEW" in res["reason"]
    
    # Trust is 0.99 but sensitive file is dict flagged
    res_dict = engine.evaluate(
        trust_score=0.99,
        mutation_score=0.99,
        test_result=True,
        patch_size=10,
        files_changed=["src/app.py"],
        sensitive_file_flags={"payment": True},
        blast_radius=0.05
    )
    assert res_dict["decision"] == "HUMAN_REVIEW"
    assert "PAYMENT_LOGIC_MODIFIED" in res_dict["risk_flags"]


def test_decision_engine_hard_restrictions():
    """
    Verify all hard restrictions trigger override.
    """
    engine = DecisionEngine()
    
    # 1. Authentication
    res_auth = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["src/auth/service.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_auth["decision"] == "HUMAN_REVIEW"
    assert "AUTHENTICATION_MODIFIED" in res_auth["risk_flags"]
    
    # 2. Authorization
    res_authz = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["src/rbac_permission.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_authz["decision"] == "HUMAN_REVIEW"
    assert "AUTHORIZATION_MODIFIED" in res_authz["risk_flags"]

    # 3. Payments
    res_pay = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["src/stripe_checkout.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_pay["decision"] == "HUMAN_REVIEW"
    assert "PAYMENT_LOGIC_MODIFIED" in res_pay["risk_flags"]

    # 4. Database migrations
    res_mig = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["alembic/versions/123_schema.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_mig["decision"] == "HUMAN_REVIEW"
    assert "DATABASE_MIGRATION_MODIFIED" in res_mig["risk_flags"]

    # 5. Secrets
    res_sec = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["config/secrets.json"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_sec["decision"] == "HUMAN_REVIEW"
    assert "SECRETS_MODIFIED" in res_sec["risk_flags"]

    # 6. Infrastructure
    res_infra = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["docker-compose.yml"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_infra["decision"] == "HUMAN_REVIEW"
    assert "INFRASTRUCTURE_MODIFIED" in res_infra["risk_flags"]

    # 7. Security Policies
    res_sec_p = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["csp_policies.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_sec_p["decision"] == "HUMAN_REVIEW"
    assert "SECURITY_POLICIES_MODIFIED" in res_sec_p["risk_flags"]

    # 8. Large Refactors
    res_large = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=250,
        files_changed=["src/a.py", "src/b.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_large["decision"] == "HUMAN_REVIEW"
    assert "LARGE_REFACTOR" in res_large["risk_flags"]

    # 9. Configured Restricted Files
    policy = {"restricted_files": ["sensitive/*.py"]}
    res_cfg = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["sensitive/secret_api.py"], sensitive_file_flags=False, blast_radius=0.1,
        repository_policy=policy
    )
    assert res_cfg["decision"] == "HUMAN_REVIEW"
    assert "RESTRICTED_FILES_MODIFIED" in res_cfg["risk_flags"]


def test_decision_engine_critical_test_failures():
    """
    Verify test or CI failures trigger REJECT regardless of trust score.
    """
    engine = DecisionEngine()
    
    # 1. Local tests fail
    res_test = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=False, patch_size=5,
        files_changed=["src/utils.py"], sensitive_file_flags=False, blast_radius=0.1
    )
    assert res_test["decision"] == "REJECT"
    assert "TEST_SUITE_FAILED" in res_test["risk_flags"]

    # 2. CI status failure
    res_ci = engine.evaluate(
        trust_score=0.99, mutation_score=0.95, test_result=True, patch_size=5,
        files_changed=["src/utils.py"], sensitive_file_flags=False, blast_radius=0.1,
        ci_status="FAILURE"
    )
    assert res_ci["decision"] == "REJECT"
    assert "CI_PIPELINE_FAILED" in res_ci["risk_flags"]


# ----------------- DB and API Integration Tests -----------------

async def seed_data_for_test(session: AsyncSession):
    org = models.Organization(id="org_test", name="Test Org")
    session.add(org)
    
    usr = models.User(id="usr_test", email="test@org.com", name="Test User")
    session.add(usr)
    
    mem = models.Membership(id="mem_test", organization_id="org_test", user_id="usr_test", role="OWNER")
    session.add(mem)
    
    proj = models.Project(id="proj_test", organization_id="org_test", name="Test Proj", repository="test/repo")
    session.add(proj)
    
    cand = models.PatchCandidate(
        id="patch_test_123",
        organization_id="org_test",
        incident_id="inc_test_123",
        diff="diff --git a/src/utils.py b/src/utils.py",
        explanation="mock explanation"
    )
    session.add(cand)
    await session.commit()


def test_evaluate_decision_api_endpoint():
    """
    Verify that evaluating and creating automated decisions via REST API works,
    persists in the DB, and returns the expected payload with all new columns.
    """
    # 1. Seed
    async def run_seed():
        async with TestSessionLocal() as session:
            await seed_data_for_test(session)
    run_sync(run_seed())
    
    from auth.dependencies import require_membership, require_role
    
    app.dependency_overrides[require_membership] = lambda: models.Membership(
        id="mem_test", organization_id="org_test", user_id="usr_test", role="OWNER"
    )
    app.dependency_overrides[require_role(["OWNER", "ADMIN", "REVIEWER"])] = lambda: models.Membership(
        id="mem_test", organization_id="org_test", user_id="usr_test", role="OWNER"
    )
    
    try:
        # High trust score but infrastructure changed (forces HUMAN_REVIEW)
        payload = {
            "patch_candidate_id": "patch_test_123",
            "trust_score": 0.95,
            "mutation_score": 0.90,
            "test_result": True,
            "patch_size": 12,
            "files_changed": ["Dockerfile"],
            "sensitive_file_flags": False,
            "blast_radius": 0.1,
            "repository_policy": {
                "auto_merge_threshold": 0.90,
                "human_review_threshold": 0.70
            },
            "ci_status": "SUCCESS"
        }
        
        headers = {
            "X-User-ID": "usr_test",
            "X-Organization-ID": "org_test"
        }
        
        response = client.post("/api/v1/decisions/evaluate", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        
        data = response.json()
        assert data["action"] == "HUMAN_REVIEW"
        assert data["status"] == "PENDING_REVIEW"
        assert "INFRASTRUCTURE_MODIFIED" in data["risk_flags"]
        assert data["policy_version"] == "v1"
        assert data["inputs"]["trust_score"] == 0.95
        assert data["actor_system"] == "system"
        
        # Verify persistence in database
        async def verify_db():
            async with TestSessionLocal() as session:
                from sqlalchemy.future import select
                stmt = select(models.Decision).where(models.Decision.id == data["id"])
                res = await session.execute(stmt)
                db_dec = res.scalar_one_or_none()
                
                assert db_dec is not None
                assert db_dec.action == "HUMAN_REVIEW"
                assert db_dec.policy_version == "v1"
                assert db_dec.actor_system == "system"
                assert db_dec.inputs["patch_size"] == 12
                assert len(db_dec.policy_checks) > 0
                assert "INFRASTRUCTURE_MODIFIED" in db_dec.risk_flags
                
        run_sync(verify_db())
        
    finally:
        app.dependency_overrides.clear()
