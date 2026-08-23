import logging
import os
import sys
from pathlib import Path

# Ensure all internal packages and apps/api are in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
api_dir = os.path.join(root_dir, "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

packages_dir = os.path.join(root_dir, "packages")
if os.path.isdir(packages_dir):
    for pkg in os.listdir(packages_dir):
        pkg_path = os.path.join(packages_dir, pkg)
        if os.path.isdir(pkg_path) and pkg_path not in sys.path:
            sys.path.insert(0, pkg_path)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from shared import setup_logging
from config import settings
from database import engine, Base
import routes.health
import routes.incidents
import routes.sandbox
import routes.webhooks


# Configure structured JSON logging
setup_logging(service_name="api-service", level=settings.LOG_LEVEL)
logger = logging.getLogger("api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up API service...", extra={"environment": settings.ENVIRONMENT})
    # Create tables automatically on startup to ensure database connectivity and readiness
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            # Simple column addition checks for SQLite / PostgreSQL
            for column, col_type in [
                ("policy_version", "VARCHAR(50)"),
                ("inputs", "JSON"),
                ("actor_system", "VARCHAR(100)"),
                ("policy_checks", "JSON"),
                ("risk_flags", "JSON")
            ]:
                try:
                    # In SQLite, JSON type is handled as TEXT, in Postgres as JSON.
                    await conn.execute(text(f"ALTER TABLE decisions ADD COLUMN {column} {col_type}"))
                    logger.info(f"Added column {column} to decisions table.")
                except Exception as ex:
                    # Column likely already exists or table does not support it
                    logger.debug(f"Column {column} check: {ex}")
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database tables: {e}", exc_info=True)
    yield
    logger.info("Shutting down API service...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Set up CORS dynamically from configuration
origins = [o.strip() for o in getattr(settings, "ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.health.router, tags=["Health"])
app.include_router(routes.incidents.router, prefix="/api/v1", tags=["Incidents & Projects"])
app.include_router(routes.sandbox.router, prefix="/api/v1", tags=["Sandbox Manager"])
app.include_router(routes.webhooks.router, prefix="/api/v1", tags=["GitHub Webhooks"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Received request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"Request completed with status code: {response.status_code}")
        return response
    except Exception as exc:
        logger.exception(f"Unhandled exception in request {request.method} {request.url.path}: {exc}")
        raise exc


# Serve static frontend assets and fallback to index.html for client-side routing
frontend_path = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_path.exists():
    assets_path = frontend_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        logger.info(f"Mounted static assets at {assets_path}")
    
    @app.get("/{catchall:path}")
    async def serve_frontend(catchall: str = ""):
        # Avoid intercepting API routes or docs if they are not matched (though routers match first)
        if catchall.startswith("api/") or catchall == "docs" or catchall == "redoc" or catchall == "openapi.json":
            return FileResponse(frontend_path / "index.html") # default fallback
        
        file_path = frontend_path / catchall
        if catchall and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_path / "index.html")
    logger.info(f"Configured catch-all route for index.html at {frontend_path}")
else:
    logger.warning("Frontend build directory not found; static files will not be served.")

