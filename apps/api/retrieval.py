import os
import hashlib
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from config import settings

logger = logging.getLogger("api.retrieval")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def to_list(val) -> List[float]:
    if not val:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            try:
                return [float(x) for x in val.strip("[]").split(",") if x.strip()]
            except Exception:
                return []
    if hasattr(val, "tolist"):
        return val.tolist()
    try:
        return list(val)
    except Exception:
        return []



def get_deterministic_mock_embedding(text: str) -> List[float]:
    """
    Generates a deterministic 1536-dimensional unit-length embedding vector
    based on the hash of the input text.
    """
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    seed = int(h[:8], 16)
    
    # Linear Congruential Generator (LCG)
    a = 1664525
    c = 1013904223
    m = 2**32
    
    x = seed
    vector = []
    sq_sum = 0.0
    for _ in range(1536):
        x = (a * x + c) % m
        val = (x / m) * 2.0 - 1.0  # value in [-1.0, 1.0]
        vector.append(val)
        sq_sum += val * val
        
    norm = sq_sum ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def generate_embedding(text: str) -> List[float]:
    """
    Generates a 1536-dimensional embedding.
    Uses OpenAI API if key is valid (not 'mock') and client is installed,
    otherwise falls back to deterministic mock embeddings.
    """
    api_key = os.getenv("OPENAI_API_KEY", "mock")
    if os.getenv("FAST_RECOVERY_MODE", "true").lower() == "true" or os.getenv("EMBEDDING_PROVIDER", "").lower() == "mock" or os.getenv("GITHUB_MOCK", "false").lower() == "true" or api_key == "mock" or api_key.startswith("sk-placeholder") or api_key.startswith("your_"):
        return get_deterministic_mock_embedding(text)
    if api_key and OpenAI is not None:
        try:
            client = OpenAI(api_key=api_key, timeout=3.0)
            response = client.embeddings.create(
                input=[text],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Failed to generate OpenAI embedding: {e}. Falling back to mock.")
            
    return get_deterministic_mock_embedding(text)


def dot_product(v1: List[float], v2: List[float]) -> float:
    return sum(x * y for x, y in zip(v1, v2))


def magnitude(v: List[float]) -> float:
    return sum(x * x for x in v) ** 0.5


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    m1 = magnitude(v1)
    m2 = magnitude(v2)
    if m1 == 0.0 or m2 == 0.0:
        return 0.0
    return dot_product(v1, v2) / (m1 * m2)


async def store_historical_record(
    db: AsyncSession,
    organization_id: Any,
    record_data: Dict[str, Any]
) -> models.HistoricalRecoveryRecord:
    """
    Computes an embedding for useful incident context and stores a
    HistoricalRecoveryRecord in the database.
    """
    incident_info = record_data.get("incident", {})
    exception_type = incident_info.get("exception_type", "")
    exception_message = incident_info.get("exception_message", "")
    stack_trace = record_data.get("stack_trace", "")
    
    # Useful incident context string for embeddings
    context_text = f"Incident: {exception_type}: {exception_message}\nStack Trace:\n{stack_trace}"
    embedding = generate_embedding(context_text)
    
    record_id = f"rec_{uuid.uuid4().hex[:8]}"
    db_record = models.HistoricalRecoveryRecord(
        id=record_id,
        organization_id=str(organization_id),
        incident_id=incident_info.get("id"),
        incident=incident_info,
        stack_trace=stack_trace,
        fault_location=record_data.get("fault_location", {}),
        patch=record_data.get("patch", ""),
        outcome=record_data.get("outcome", ""),
        trust_score=float(record_data.get("trust_score", 0.0)),
        human_decision=record_data.get("human_decision", ""),
        final_result=record_data.get("final_result", ""),
        embedding=embedding,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record


async def query_similar_recovery_records(
    db: AsyncSession,
    organization_id: Any,
    exception_type: str,
    exception_message: str,
    stack_trace: str,
    limit: int = 5,
    similarity_threshold: float = 0.0,
    shared_knowledge_mode: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Performs pgvector similarity search (with SQLite fallback) to retrieve
    similar historical incident recovery records. Enforces organization-level isolation.
    """
    if shared_knowledge_mode is None:
        # Fallback to config setting
        shared_knowledge_mode = getattr(settings, "SHARED_KNOWLEDGE_MODE", False)
        
    context_text = f"Incident: {exception_type}: {exception_message}\nStack Trace:\n{stack_trace}"
    query_embedding = generate_embedding(context_text)
    
    is_sqlite = db.bind.dialect.name == "sqlite"
    
    results = []
    
    if is_sqlite:
        # Fetch organization-isolated records and compute similarity in Python
        stmt = select(models.HistoricalRecoveryRecord)
        if not shared_knowledge_mode:
            stmt = stmt.where(models.HistoricalRecoveryRecord.organization_id == organization_id)
            
        db_res = await db.execute(stmt)
        records = db_res.scalars().all()
        
        scored = []
        for rec in records:
            rec_emb = to_list(rec.embedding)
            if not rec_emb:
                # Generate deterministic fallback
                rec_context = f"Incident: {rec.incident.get('exception_type', '')}: {rec.incident.get('exception_message', '')}\nStack Trace:\n{rec.stack_trace}"
                rec_emb = get_deterministic_mock_embedding(rec_context)
                
            sim = cosine_similarity(query_embedding, rec_emb)
            if sim >= similarity_threshold:
                scored.append((rec, sim))
                
        # Sort descending by similarity
        scored.sort(key=lambda x: x[1], reverse=True)
        for rec, sim in scored[:limit]:
            results.append({
                "similarity_score": sim,
                "incident_id": rec.incident.get("id") or rec.id,
                "previous_fault_location": rec.fault_location,
                "previous_patch": rec.patch,
                "outcome": rec.outcome,
                "trust_score": rec.trust_score,
                "human_decision": rec.human_decision
            })
    else:
        # PostgreSQL with pgvector distance operator (1 - cosine_distance)
        similarity_expr = (1.0 - models.HistoricalRecoveryRecord.embedding.cosine_distance(query_embedding)).label("similarity")
        stmt = select(models.HistoricalRecoveryRecord, similarity_expr)
        
        if not shared_knowledge_mode:
            stmt = stmt.where(models.HistoricalRecoveryRecord.organization_id == organization_id)
            
        if similarity_threshold > 0.0:
            stmt = stmt.where(1.0 - models.HistoricalRecoveryRecord.embedding.cosine_distance(query_embedding) >= similarity_threshold)
            
        stmt = stmt.order_by(models.HistoricalRecoveryRecord.embedding.cosine_distance(query_embedding).asc())
        stmt = stmt.limit(limit)
        
        db_res = await db.execute(stmt)
        rows = db_res.all()
        
        for rec, sim in rows:
            results.append({
                "similarity_score": float(sim),
                "incident_id": rec.incident.get("id") or rec.id,
                "previous_fault_location": rec.fault_location,
                "previous_patch": rec.patch,
                "outcome": rec.outcome,
                "trust_score": rec.trust_score,
                "human_decision": rec.human_decision
            })
            
    return results
