import logging
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis
from celery_app import celery_app
from database import get_db

router = APIRouter()
logger = logging.getLogger("health")

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "database": "unhealthy",
        "redis": "unhealthy",
        "celery": "unhealthy"
    }
    
    # 1. Check Database
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}", extra={"context": "health_check"})
        health_status["status"] = "unhealthy"

    # 2. Check Redis
    def check_redis():
        try:
            # pyrefly: ignore [bad-argument-type]
            r = redis.from_url(celery_app.conf.broker_url, protocol=2, socket_timeout=0.5, socket_connect_timeout=0.5)
            return r.ping()
        except Exception as e:
            logger.debug(f"Redis ping error: {e}")
            return False

    try:
        redis_ok = await asyncio.wait_for(asyncio.to_thread(check_redis), timeout=1.0)
        health_status["redis"] = "healthy" if redis_ok else "unhealthy"
    except Exception:
        health_status["redis"] = "unhealthy"

    # 3. Check Celery Workers
    health_status["celery"] = "no_workers"
    if health_status["redis"] == "healthy":
        def check_celery():
            try:
                i = celery_app.control.inspect(timeout=0.1)
                pings = i.ping() if i else None
                return "healthy" if pings else "no_workers"
            except Exception:
                return "no_workers"
        try:
            health_status["celery"] = await asyncio.wait_for(asyncio.to_thread(check_celery), timeout=0.3)
        except Exception:
            health_status["celery"] = "no_workers"

    # Top-level status is healthy if database is operational
    if health_status["database"] == "healthy":
        health_status["status"] = "healthy"

    return health_status

