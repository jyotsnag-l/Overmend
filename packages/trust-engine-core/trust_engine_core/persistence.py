import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

logger = logging.getLogger("trust_engine_core.persistence")

# Fallback engine creation if main app database is not available
def _get_fallback_session_maker() -> async_sessionmaker[AsyncSession]:
    db_url = os.getenv("DATABASE_URL") or os.getenv("TRUST_ENGINE_DATABASE_URL") or "sqlite+aiosqlite:///test_recovery.db"
    engine = create_async_engine(db_url, echo=False, future=True)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    """
    Tries to import the API's AsyncSessionLocal. If unavailable, falls back to a locally configured engine.
    """
    try:
        from database import AsyncSessionLocal
        return AsyncSessionLocal()
    except ImportError:
        logger.info("Could not import AsyncSessionLocal from API database module. Using fallback session maker.")
        session_maker = _get_fallback_session_maker()
        return session_maker()

async def persist_evaluation(
    trust_score: float,
    mutation_score: float,
    evidence: Dict[str, Any],
    mutations: List[Dict[str, Any]],
    patch_candidate_id: Optional[str] = None,
    organization_id: Optional[str] = None
) -> str:
    """
    Persists a trust evaluation and its mutations to the database.
    Returns the generated evaluation ID.
    """
    evaluation_id = f"eval_{uuid.uuid4().hex[:8]}"
    
    try:
        import models
    except ImportError:
        logger.warning("Could not import models from API. Persistence skipped.")
        return evaluation_id

    session = await get_session()
    async with session:
        try:
            # Create TrustEvaluation record
            db_eval = models.TrustEvaluation(
                id=evaluation_id,
                organization_id=organization_id,
                patch_candidate_id=patch_candidate_id,
                trust_score=trust_score,
                mutation_score=mutation_score,
                evidence=evidence,
                created_at=datetime.now(timezone.utc)
            )
            session.add(db_eval)

            # Create Mutation records
            for mut in mutations:
                db_mut = models.Mutation(
                    id=mut.get("id") or f"mut_{uuid.uuid4().hex[:8]}",
                    organization_id=organization_id,
                    trust_evaluation_id=evaluation_id,
                    file_path=mut.get("file", ""),
                    line_number=mut.get("line", 0),
                    original_operator=mut.get("original", ""),
                    mutated_operator=mut.get("mutated", ""),
                    status=mut.get("status", "UNKNOWN"),
                    created_at=datetime.now(timezone.utc)
                )
                session.add(db_mut)

            await session.commit()
            logger.info(f"Successfully persisted trust evaluation {evaluation_id} with {len(mutations)} mutations.")
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to persist trust evaluation: {e}", exc_info=True)
            raise e
            
    return evaluation_id
