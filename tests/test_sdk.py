import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from recovery_sdk import monitor
from recovery_sdk.monitor import ExceptionMonitor, get_git_commit
from recovery_sdk.integrations.fastapi import RecoveryMiddleware

@pytest.mark.asyncio
async def test_sdk_monitor_capture_exception() -> None:
    # Instantiate a clean ExceptionMonitor to avoid sharing global state
    test_monitor = ExceptionMonitor()
    
    # Mock send method to verify it is called
    test_monitor._send_with_retry = AsyncMock(return_value=True)
    
    # Start monitor
    test_monitor.start(project_id="test_proj", environment="test_env", api_url="http://mock-api")
    
    try:
        raise ValueError("Simulated operational error")
    except Exception as e:
        test_monitor.capture_exception(e, context={"extra_key": "extra_value"})

    # Wait for the worker thread to call send
    for _ in range(40):
        if test_monitor._send_with_retry.called:
            break
        await asyncio.sleep(0.05)

    assert test_monitor._send_with_retry.called
    call_args = test_monitor._send_with_retry.call_args[0]
    payload = call_args[1]
    
    assert payload["project_id"] == "test_proj"
    assert payload["exception_type"] == "ValueError"
    assert payload["exception_message"] == "Simulated operational error"
    assert payload["environment"] == "test_env"
    assert payload["context"]["extra_key"] == "extra_value"
    assert "file" in payload
    assert "line" in payload
    assert "function" in payload
    
    test_monitor.stop()


def test_git_commit_resolution() -> None:
    commit = get_git_commit()
    assert commit is not None


def test_fastapi_middleware_integration() -> None:
    test_monitor = ExceptionMonitor()
    test_monitor._send_with_retry = AsyncMock(return_value=True)
    
    # Override global monitor startup by manually starting test_monitor
    test_monitor.start(project_id="test_proj", api_url="http://mock-api")
    
    app = FastAPI()
    
    # Add middleware pointing to our test monitor's parameters
    app.add_middleware(
        RecoveryMiddleware,
        project_id="test_proj",
        api_url="http://mock-api"
    )
    
    # Patch global monitor capture_exception to call our test monitor
    with patch("recovery_sdk.integrations.fastapi.monitor.capture_exception", side_effect=test_monitor.capture_exception):
        @app.get("/raise")
        def raise_route():
            raise RuntimeError("FastAPI route error")

        client = TestClient(app)
        
        # TestClient propagates unhandled exceptions, so let's catch it here
        with pytest.raises(RuntimeError):
            client.get("/raise")

        # Let the background thread process the event queue
        import time
        for _ in range(40):
            if test_monitor._send_with_retry.called:
                break
            time.sleep(0.05)

        assert test_monitor._send_with_retry.called
        payload = test_monitor._send_with_retry.call_args[0][1]
        assert payload["exception_type"] == "RuntimeError"
        assert payload["exception_message"] == "FastAPI route error"
        assert payload["request_metadata"]["url"].endswith("/raise")
        assert payload["request_metadata"]["method"] == "GET"
        
    test_monitor.stop()
