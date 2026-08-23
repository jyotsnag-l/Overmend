import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from main import app
from database import get_db

client = TestClient(app)

def test_openapi_docs() -> None:
    """
    Verify OpenAPI schemas and documentation endpoint can be fetched.
    """
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()

@patch("routes.health.redis.from_url")
def test_health_endpoint_healthy(mock_redis_from_url: MagicMock) -> None:
    """
    Verify health endpoint returns status data when dependencies are healthy.
    """
    # Mock database session
    mock_db = AsyncMock()
    mock_db.execute.return_value = None

    # Mock Redis client
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis_from_url.return_value = mock_redis

    # Mock Celery worker inspection
    mock_ping = {"worker@hostname": "pong"}
    with patch("routes.health.celery_app.control.inspect") as mock_inspect:
        mock_ins_instance = MagicMock()
        mock_ins_instance.ping.return_value = mock_ping
        mock_inspect.return_value = mock_ins_instance

        # Override DB dependency
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "healthy"
            assert data["redis"] == "healthy"
            assert data["celery"] == "healthy"
        finally:
            app.dependency_overrides.clear()

def test_create_project_mocked() -> None:
    """
    Verify project creation route.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    async def mock_refresh(instance):
        from datetime import datetime, timezone
        instance.created_at = datetime.now(timezone.utc)
    mock_db.refresh = mock_refresh
    
    from auth.dependencies import require_membership
    import models
    
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_membership] = lambda: models.Membership(
        id="mem_test", organization_id="org_test", user_id="usr_test", role="OWNER"
    )
    try:
        payload = {
            "id": "proj_test",
            "name": "Test Repository",
            "repository": "test/repo"
        }
        headers = {
            "X-User-ID": "usr_test",
            "X-User-Email": "test@org.com",
            "X-Organization-ID": "org_test"
        }
        response = client.post("/api/v1/projects", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "proj_test"
        assert data["name"] == "Test Repository"
        assert data["repository"] == "test/repo"
    finally:
        app.dependency_overrides.clear()
