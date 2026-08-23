from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from recovery_sdk import monitor

class RecoveryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, project_id: str, environment: str = "production", api_url: str = "http://localhost:8000"):
        super().__init__(app)
        # Start monitor singleton
        monitor.start(project_id=project_id, environment=environment, api_url=api_url)

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            # Capture exception with request context
            monitor.capture_exception(exc, request=request)
            # Re-raise so FastAPI or Starlette can process it
            raise exc from None
