import pytest
import os
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from main import app
from database import get_db, Base
import models

# Set Celery bypass
os.environ["BYPASS_CELERY"] = "true"

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Helper to run async code synchronously
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
    # Setup tables
    async def create_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    run_sync(create_tables())
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    app.dependency_overrides.clear()
    
    # Drop tables
    async def drop_tables():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    run_sync(drop_tables())


# Seeding helpers (now run synchronously using run_sync)
def create_user(user_id: str, email: str, name: str) -> models.User:
    async def _run():
        async with TestSessionLocal() as db:
            user = models.User(id=user_id, email=email, name=name)
            db.add(user)
            await db.commit()
            return user
    return run_sync(_run())

def create_org(org_id: str, name: str) -> models.Organization:
    async def _run():
        async with TestSessionLocal() as db:
            org = models.Organization(id=org_id, name=name)
            db.add(org)
            await db.commit()
            return org
    return run_sync(_run())

def create_membership(org_id: str, user_id: str, role: str) -> models.Membership:
    async def _run():
        import uuid
        async with TestSessionLocal() as db:
            membership = models.Membership(
                id=f"mem_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                user_id=user_id,
                role=role
            )
            db.add(membership)
            await db.commit()
            return membership
    return run_sync(_run())

def create_project(org_id: str, project_id: str, name: str, repo: str) -> models.Project:
    async def _run():
        async with TestSessionLocal() as db:
            project = models.Project(id=project_id, organization_id=org_id, name=name, repository=repo)
            db.add(project)
            await db.commit()
            return project
    return run_sync(_run())

def create_incident(org_id: str, project_id: str, incident_id: str) -> models.Incident:
    async def _run():
        async with TestSessionLocal() as db:
            incident = models.Incident(
                id=incident_id,
                organization_id=org_id,
                project_id=project_id,
                exception_type="ValueError",
                exception_message="Test operational failure",
                stack_trace="Traceback: ...",
                fingerprint=f"ValueError:{incident_id}",
                status="INVESTIGATING"
            )
            db.add(incident)
            await db.commit()
            return incident
    return run_sync(_run())

def create_patch(org_id: str, incident_id: str, patch_id: str) -> models.PatchCandidate:
    async def _run():
        async with TestSessionLocal() as db:
            patch = models.PatchCandidate(
                id=patch_id,
                organization_id=org_id,
                incident_id=incident_id,
                diff="--- a/file.py\n+++ b/file.py...",
                explanation="Fixed a bug"
            )
            db.add(patch)
            await db.commit()
            return patch
    return run_sync(_run())


# Sync Test Cases
def test_organization_isolation() -> None:
    """
    PROVES: 1. Users cannot access another organization's data.
    """
    client = TestClient(app)

    # Seed data
    create_user("usr_a", "user_a@org.com", "User A")
    create_org("org_a", "Organization A")
    create_membership("org_a", "usr_a", "VIEWER")

    create_user("usr_b", "user_b@org.com", "User B")
    create_org("org_b", "Organization B")
    create_membership("org_b", "usr_b", "VIEWER")
    create_project("org_b", "proj_b", "Project B", "org-b/repo-b")

    # User A tries to list projects of Org B
    headers_a_on_b = {
        "X-User-ID": "usr_a",
        "X-User-Email": "user_a@org.com",
        "X-Organization-ID": "org_b"
    }
    response = client.get("/api/v1/projects", headers=headers_a_on_b)
    # Must fail because User A is not a member of Org B
    assert response.status_code == 403
    assert "not a member of Organization org_b" in response.json()["detail"]

    # User B tries to list projects of Org B
    headers_b_on_b = {
        "X-User-ID": "usr_b",
        "X-User-Email": "user_b@org.com",
        "X-Organization-ID": "org_b"
    }
    response = client.get("/api/v1/projects", headers=headers_b_on_b)
    # Must succeed
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "proj_b"


def test_viewer_cannot_approve_patch() -> None:
    """
    PROVES: 2. Viewer cannot approve a patch.
    """
    client = TestClient(app)

    # Seed data
    create_user("usr_viewer", "viewer@org.com", "Viewer User")
    create_org("org_test", "Test Org")
    create_membership("org_test", "usr_viewer", "VIEWER")
    
    create_project("org_test", "proj_1", "Project 1", "org/repo1")
    create_incident("org_test", "proj_1", "inc_1")
    create_patch("org_test", "inc_1", "pat_1")

    # Viewer tries to approve patch candidate
    headers = {
        "X-User-ID": "usr_viewer",
        "X-User-Email": "viewer@org.com",
        "X-Organization-ID": "org_test"
    }
    payload = {
        "patch_candidate_id": "pat_1",
        "status": "APPROVED",
        "reason": "Test approval"
    }
    response = client.post("/api/v1/decisions", json=payload, headers=headers)
    
    # Must fail with 403
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]
    assert "requires one of roles" in response.json()["detail"]


def test_engineer_cannot_perform_owner_only_actions() -> None:
    """
    PROVES: 3. Engineer cannot perform Owner-only actions (e.g. updating organization settings).
    """
    client = TestClient(app)

    # Seed data
    create_user("usr_eng", "eng@org.com", "Engineer User")
    create_org("org_test", "Test Org")
    create_membership("org_test", "usr_eng", "ENGINEER")

    # Engineer tries to update organization settings (Owner-only)
    headers = {
        "X-User-ID": "usr_eng",
        "X-User-Email": "eng@org.com",
        "X-Organization-ID": "org_test"
    }
    response = client.post("/api/v1/organizations/org_test/settings", json={"theme": "dark"}, headers=headers)
    
    # Must fail with 403
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]
    assert "requires one of roles ['OWNER']" in response.json()["detail"]


def test_reviewer_can_approve_reject_patches() -> None:
    """
    PROVES: 4. Reviewer can approve/reject patches.
    """
    client = TestClient(app)

    # Seed data
    create_user("usr_reviewer", "reviewer@org.com", "Reviewer User")
    create_org("org_test", "Test Org")
    create_membership("org_test", "usr_reviewer", "REVIEWER")
    
    create_project("org_test", "proj_1", "Project 1", "org/repo1")
    create_incident("org_test", "proj_1", "inc_1")
    create_patch("org_test", "inc_1", "pat_1")

    # Reviewer approves patch candidate
    headers = {
        "X-User-ID": "usr_reviewer",
        "X-User-Email": "reviewer@org.com",
        "X-Organization-ID": "org_test"
    }
    payload = {
        "patch_candidate_id": "pat_1",
        "status": "APPROVED",
        "reason": "Reviewer approved patch"
    }
    response = client.post("/api/v1/decisions", json=payload, headers=headers)
    
    # Must succeed
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["action"] == "AUTO_MERGE"
    assert data["decided_by"] == "usr_reviewer"


def test_audit_events_are_persisted() -> None:
    """
    PROVES: 5. All audit events are persisted in the database.
    """
    client = TestClient(app)

    # 1. Create Organization (generates AuditLog entry)
    headers_creator = {
        "X-User-ID": "usr_owner",
        "X-User-Email": "owner@org.com",
        "X-User-Name": "Owner User"
    }
    response = client.post("/api/v1/organizations", json={"name": "Audit Org", "id": "org_audit"}, headers=headers_creator)
    assert response.status_code == 200

    # 2. Create Project (generates AuditLog entry)
    headers_owner = {
        "X-User-ID": "usr_owner",
        "X-User-Email": "owner@org.com",
        "X-Organization-ID": "org_audit"
    }
    response = client.post("/api/v1/projects", json={"id": "proj_audit", "name": "Audit Project", "repository": "audit/repo"}, headers=headers_owner)
    assert response.status_code == 200

    # Fetch audit logs for this organization
    response = client.get("/api/v1/audit-logs", headers=headers_owner)
    assert response.status_code == 200
    audit_logs = response.json()

    # Verify that BOTH CREATE_ORGANIZATION and CREATE_PROJECT audit events are saved and returned
    assert len(audit_logs) == 2
    
    actions = [log["action"] for log in audit_logs]
    assert "CREATE_PROJECT" in actions
    assert "CREATE_ORGANIZATION" in actions

    # Verify log detail properties
    project_log = next(log for log in audit_logs if log["action"] == "CREATE_PROJECT")
    assert project_log["resource_type"] == "Project"
    assert project_log["resource_id"] == "proj_audit"
    assert project_log["user_id"] == "usr_owner"
    assert project_log["details"]["name"] == "Audit Project"


def test_jwt_auth_provider_verification() -> None:
    """
    PROVES: JWTAuthProvider correctly signs, validates, and rejects JWT tokens.
    """
    from auth.provider import JWTAuthProvider, UserPrincipal
    
    provider = JWTAuthProvider(secret_key="test-secret-key-1234567890-32bytes-long-secret", algorithm="HS256")
    
    # 1. Generate valid token
    token = provider.create_token({
        "sub": "usr_jwt_123",
        "email": "jwtuser@org.com",
        "name": "JWT User",
        "role": "ENGINEER"
    }, expires_in=300)
    
    assert token is not None
    assert isinstance(token, str)
    
    # 2. Test mock request with valid Bearer token
    class MockRequest:
        def __init__(self, token_str):
            self.headers = {"Authorization": f"Bearer {token_str}"}
            
    req = MockRequest(token)
    principal = run_sync(provider.authenticate(req))
    
    assert principal is not None
    assert principal.id == "usr_jwt_123"
    assert principal.email == "jwtuser@org.com"
    assert principal.name == "JWT User"
    
    # 3. Invalid signature must fail
    invalid_provider = JWTAuthProvider(secret_key="wrong-secret-key-1234567890-32bytes-wrong", algorithm="HS256")
    failed_principal = run_sync(invalid_provider.authenticate(req))
    assert failed_principal is None

