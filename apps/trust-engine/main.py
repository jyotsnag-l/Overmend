import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from shared import setup_logging
import trust_engine_core

setup_logging(service_name="trust-engine-service", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("trust_engine_service")

app = FastAPI(
    title="Trust Engine Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EvaluateRequest(BaseModel):
    repository: str = Field(description="Absolute path to the repository directory or a cloneable URL")
    patch_diff: str = Field(description="Unified diff of the candidate patch")
    test_command: str = Field(default="pytest", description="Command to execute the test suite")
    patch_candidate_id: Optional[str] = Field(default=None, description="Optional DB Patch Candidate ID to associate")
    organization_id: Optional[str] = Field(default=None, description="Optional DB Organization ID to associate")
    historical_success: float = Field(default=1.0, ge=0.0, le=1.0, description="Rate of historical recovery success")
    blast_radius: float = Field(default=0.0, ge=0.0, le=1.0, description="Affected ratio/blast radius")
    sensitive_file_flag: bool = Field(default=False, description="Flag indicating if a sensitive file was modified")
    scorer_config: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom weights and thresholds config")

class MutationResult(BaseModel):
    id: str
    file: str
    line: int
    category: str
    original: str
    mutated: str
    status: str
    test_output: str
    duration_ms: int
    explanation: Optional[str] = None

class EvaluateResponse(BaseModel):
    evaluation_id: str
    mutation_score: float
    confidence: float
    evidence: Dict[str, Any]
    mutations: List[MutationResult]
    risk_flags: List[str]
    recommendation: str

@app.post("/v1/evaluate", response_model=EvaluateResponse)
async def evaluate_candidate_patch(payload: EvaluateRequest):
    """
    Evaluates a candidate patch using targeted mutation testing,
    calculating the trust score and returning a recommendation.
    """
    logger.info(f"Received evaluation request for repository={payload.repository}")
    
    # Simple validation that the repository exists on local filesystem (if it's a path)
    if not payload.repository.startswith("http") and not os.path.exists(payload.repository):
        raise HTTPException(
            status_code=400,
            detail=f"Repository path '{payload.repository}' does not exist on this machine."
        )

    try:
        # Run evaluation pipeline (blocks running tests, so runs synchronously inside FastAPI thread pool worker)
        results = trust_engine_core.evaluate_patch(
            repository=payload.repository,
            patch_diff=payload.patch_diff,
            test_command=payload.test_command,
            patch_candidate_id=payload.patch_candidate_id,
            organization_id=payload.organization_id,
            scorer_config=payload.scorer_config,
            historical_success=payload.historical_success,
            blast_radius=payload.blast_radius,
            sensitive_file_flag=payload.sensitive_file_flag
        )
        return results
    except Exception as e:
        logger.error(f"Error evaluating patch: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during evaluation: {str(e)}"
        )
