import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import importlib.util

# Load trust-engine main app dynamically to avoid sys.modules conflict with apps/api/main.py
module_name = "trust_engine_service_main"
file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/trust-engine/main.py"))
spec = importlib.util.spec_from_file_location(module_name, file_path)
trust_engine_module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = trust_engine_module
spec.loader.exec_module(trust_engine_module)
app = trust_engine_module.app
from database import engine, Base, AsyncSessionLocal
import models
import trust_engine_core
from trust_engine_core.scorer import TrustScorer

client = TestClient(app)


def test_score_calculation_is_deterministic():
    """
    Verify that the scorer returns the identical score and evidence
    when run multiple times with identical inputs.
    """
    inputs = {
        "test_pass_result": True,
        "mutation_score": 0.916,
        "patch_locality": 1.0,
        "patch_size": 15,
        "files_changed": 1,
        "sensitive_file_flag": False,
        "blast_radius": 0.1,
        "historical_success": 0.95
    }
    
    scorer = TrustScorer()
    res1 = scorer.calculate_score(inputs)
    res2 = scorer.calculate_score(inputs)
    
    # Assert exact deterministic equality
    assert res1["trust_score"] == res2["trust_score"]
    assert res1["confidence"] == res2["confidence"]
    assert res1["recommendation"] == res2["recommendation"]
    assert res1["evidence"] == res2["evidence"]
    assert res1["risk_flags"] == res2["risk_flags"]


def test_evidence_explains_the_score():
    """
    Verify that the evidence explains how the score was calculated (inputs, weights, contributions).
    Also verify that weighting is not presented as scientifically optimal.
    """
    inputs = {
        "test_pass_result": True,
        "mutation_score": 0.80,
        "patch_locality": 1.0,
        "patch_size": 5,
        "files_changed": 1,
        "sensitive_file_flag": True, # penalty
        "blast_radius": 0.2,          # penalty
        "historical_success": 0.90
    }
    
    scorer = TrustScorer()
    res = scorer.calculate_score(inputs)
    evidence = res["evidence"]
    
    # 1. Inputs are recorded
    assert evidence["inputs"]["test_pass_result"] is True
    assert evidence["inputs"]["mutation_score"] == 0.80
    assert evidence["inputs"]["sensitive_file_flag"] is True

    # 2. Config weights and penalties are visible
    assert "test_pass_result" in evidence["config_weights"]
    assert "sensitive_file" in evidence["config_penalties"]
    
    # 3. Contributions and deductions are detailed
    assert "test_pass_result" in evidence["weighted_contributions"]
    assert "sensitive_file" in evidence["penalty_deductions"]
    
    # 4. Math is visible
    final_score = evidence["final_score"]
    assert final_score == res["trust_score"]
    
    # 5. Scientific disclaimer is present
    assert "disclaimer" in evidence
    assert "not scientifically optimal" in evidence["disclaimer"].lower()


@pytest.mark.asyncio
async def test_evaluate_patch_without_incident_and_persists():
    """
    Verify that:
    1. A patch can be evaluated without an Incident (i.e. patch_candidate_id/organization_id are None).
    2. The mutation results and evaluation are persisted in the DB.
    3. Surviving mutations are returned with explanations.
    """
    # Force rebuild database to apply the modified nullable schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    repo_path = os.path.abspath("demo-repo")
    
    # Candidate patch changing user_id boundary condition in users.py
    # Change user_id < 0 to user_id <= 0.
    # The tests only check get_user_profile(1) and get_user_profile(-1).
    # Mutant 'user_id < 0' (boundary change) will survive since no test queries get_user_profile(0).
    patch_diff = (
        "diff --git a/users.py b/users.py\n"
        "--- a/users.py\n"
        "+++ b/users.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def get_user_profile(user_id: int) -> dict:\n"
        "-    if user_id < 0:\n"
        "+    if user_id <= 0:\n"
        '        raise ValueError("Invalid user_id: must be non-negative")\n'
    )

    # API Request payload
    payload = {
        "repository": repo_path,
        "patch_diff": patch_diff,
        "test_command": "pytest",
        "historical_success": 0.90,
        "blast_radius": 0.1,
        "sensitive_file_flag": False
    }

    # 1. Call API POST endpoint
    response = client.post("/v1/evaluate", json=payload)
    assert response.status_code == 200, f"API failed: {response.text}"
    
    data = response.json()
    eval_id = data["evaluation_id"]
    assert eval_id.startswith("eval_")
    assert "mutation_score" in data
    assert "confidence" in data
    assert "evidence" in data
    assert "recommendation" in data
    
    # Verify mutations list is returned
    mutations = data["mutations"]
    assert len(mutations) > 0
    
    # 2. Verify surviving mutations are explicitly returned with explanations
    survived_mutations = [m for m in mutations if m["status"] == "SURVIVED"]
    assert len(survived_mutations) > 0, "Expected at least one surviving mutant (boundary condition user_id <= 0 vs < 0)"
    
    for sm in survived_mutations:
        assert "explanation" in sm
        assert "did not detect" in sm["explanation"]

    # 3. Verify results are persisted in DB
    async with AsyncSessionLocal() as session:
        # Check TrustEvaluation
        eval_stmt = select(models.TrustEvaluation).where(models.TrustEvaluation.id == eval_id)
        db_eval_res = await session.execute(eval_stmt)
        db_eval = db_eval_res.scalar_one_or_none()
        
        assert db_eval is not None
        assert db_eval.trust_score == data["evidence"]["final_score"]
        assert db_eval.mutation_score == data["mutation_score"]
        assert db_eval.patch_candidate_id is None  # Proves evaluated without incident

        # Check Mutations
        mut_stmt = select(models.Mutation).where(models.Mutation.trust_evaluation_id == eval_id)
        db_mut_res = await session.execute(mut_stmt)
        db_muts = db_mut_res.scalars().all()
        
        assert len(db_muts) == len(mutations)
        assert any(db_mut.status == "SURVIVED" for db_mut in db_muts)
        assert all(db_mut.file_path == "users.py" for db_mut in db_muts)
