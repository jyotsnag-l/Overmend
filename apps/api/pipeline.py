import re
import uuid
import logging
import hashlib
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas
from celery_app import celery_app

logger = logging.getLogger("api.pipeline")

# Severity Levels
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
CRITICAL = "CRITICAL"

# Lifecycle States
DETECTED = "DETECTED"
TRIAGED = "TRIAGED"
LOCALIZED = "LOCALIZED"
PATCH_GENERATED = "PATCH_GENERATED"
SANDBOX_RUNNING = "SANDBOX_RUNNING"
TESTED = "TESTED"
TRUST_EVALUATED = "TRUST_EVALUATED"
AUTO_MERGE = "AUTO_MERGE"
HUMAN_REVIEW = "HUMAN_REVIEW"
MERGED = "MERGED"
VERIFIED = "VERIFIED"
REJECTED = "REJECTED"
REVERTED = "REVERTED"


def parse_stack_trace(stack_trace: str) -> List[Dict[str, Any]]:
    """
    Parses a standard Python stack trace into structured frames.
    Each frame contains: file, line, function, code.
    """
    frames = []
    if not stack_trace:
        return frames

    # Pattern for Python traceback frame: File "path/to/file.py", line 12, in function_name
    pattern = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
    lines = stack_trace.splitlines()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        match = pattern.search(line)
        if match:
            file_path = match.group(1)
            line_no = int(match.group(2))
            func_name = match.group(3)
            
            # The next line usually contains the code snippet
            code_snippet = ""
            if i + 1 < len(lines) and not pattern.search(lines[i + 1]) and not lines[i + 1].strip().startswith("Traceback"):
                code_snippet = lines[i + 1].strip()
                i += 1
            
            frames.append({
                "file": file_path,
                "line": line_no,
                "function": func_name,
                "code": code_snippet
            })
        i += 1
        
    return frames


def generate_fingerprint(exception_type: str, exception_message: str, stack_frames: List[Dict[str, Any]]) -> str:
    """
    Generates a stable stack-trace fingerprint by cleaning dynamic values
    and hashing key traceback elements.
    """
    # 1. Clean dynamic values from message to avoid request-specific noise
    cleaned_msg = exception_message
    # Remove hex addresses
    cleaned_msg = re.sub(r'0x[0-9a-fA-F]+', '<hex>', cleaned_msg)
    # Remove UUIDs
    cleaned_msg = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '<uuid>', cleaned_msg)
    # Remove large groups of digits (like IDs)
    cleaned_msg = re.sub(r'\b\d{5,}\b', '<id>', cleaned_msg)
    
    # 2. Extract key features
    if stack_frames:
        # Focus on the last 5 frames of the stack trace
        frame_strs = []
        for frame in stack_frames[-5:]:
            # Clean file path to keep only relative directory/file
            file_path = frame["file"]
            # Normalize path separators
            file_path = file_path.replace("\\", "/")
            # Remove virtual environment paths or system lib path components
            if "site-packages" in file_path:
                file_path = file_path.split("site-packages/")[-1]
            elif "lib/python" in file_path:
                file_path = file_path.split("lib/python")[-1]
            else:
                # Keep last 3 path segments
                parts = file_path.split("/")
                file_path = "/".join(parts[-3:])
                
            frame_strs.append(f"{file_path}:{frame['function']}")
            
        fingerprint_raw = f"{exception_type}|" + "|".join(frame_strs)
    else:
        fingerprint_raw = f"{exception_type}|{cleaned_msg.strip()}"
        
    # Generate MD5 hash of raw fingerprint
    return hashlib.md5(fingerprint_raw.encode("utf-8")).hexdigest()


async def transition_state(
    db: AsyncSession,
    incident: models.Incident,
    to_state: str,
    user_id: Optional[str] = None,
    reason: Optional[str] = None,
    metadata_info: Optional[Dict[str, Any]] = None
) -> None:
    """
    Transition incident to a new state. Persists the transition in IncidentHistory
    and AuditLog tables.
    """
    from_state = incident.status
    if from_state == to_state:
        return
        
    incident.status = to_state
    
    # Write IncidentHistory record
    history = models.IncidentHistory(
        id=f"hist_{uuid.uuid4().hex[:8]}",
        organization_id=incident.organization_id,
        incident_id=incident.id,
        from_state=from_state,
        to_state=to_state,
        transitioned_by=user_id,
        reason=reason,
        timestamp=datetime.now(timezone.utc),
        metadata_info=metadata_info or {}
    )
    db.add(history)
    
    # Write AuditLog record
    audit = models.AuditLog(
        id=f"aud_{uuid.uuid4().hex[:8]}",
        organization_id=incident.organization_id,
        user_id=user_id,
        action="INCIDENT_STATE_TRANSITION",
        resource_type="Incident",
        resource_id=incident.id,
        details={
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason or ""
        }
    )
    db.add(audit)
    logger.info(f"Incident {incident.id} state transitioned: {from_state} -> {to_state} (Reason: {reason})")


def update_rolling_metrics(metrics: Dict[str, Any], event_time: float) -> Tuple[Dict[str, Any], float, float, float, float]:
    """
    Updates the rolling metrics bucket dictionary and calculates:
    - error frequency (occurrences in last 60 seconds)
    - rolling error rate (frequency / 60)
    - EWMA of frequency
    - z-score relative to historical buckets
    """
    # Clean up empty metrics
    if not metrics:
        metrics = {
            "timestamps": [],
            "ewma": 0.0,
            "mean": 0.0,
            "variance": 0.0,
            "m2": 0.0,
            "n_buckets": 0,
            "current_bucket_start": event_time,
            "current_bucket_count": 0
        }
        
    timestamps = metrics.get("timestamps", [])
    timestamps.append(event_time)
    
    # Prune timestamps older than 60 seconds
    cutoff = event_time - 60.0
    timestamps = [t for t in timestamps if t >= cutoff]
    metrics["timestamps"] = timestamps
    
    frequency = len(timestamps)
    rolling_rate = frequency / 60.0
    
    # Handle completed 60-second buckets incrementally
    current_bucket_start = metrics.get("current_bucket_start", event_time)
    current_bucket_count = metrics.get("current_bucket_count", 0) + 1
    
    ewma = metrics.get("ewma", 0.0)
    mean = metrics.get("mean", 0.0)
    variance = metrics.get("variance", 0.0)
    m2 = metrics.get("m2", 0.0)
    n_buckets = metrics.get("n_buckets", 0)
    
    if event_time - current_bucket_start >= 60.0:
        # Minute has passed! Commit current bucket count
        n_buckets += 1
        
        # Welford's algorithm for running mean and variance
        delta = current_bucket_count - mean
        mean += delta / n_buckets
        delta2 = current_bucket_count - mean
        m2 += delta * delta2
        variance = m2 / n_buckets if n_buckets > 0 else 0.0
        
        # Update EWMA
        if n_buckets == 1:
            ewma = float(current_bucket_count)
        else:
            ewma = 0.2 * current_bucket_count + 0.8 * ewma
            
        # Reset current bucket
        current_bucket_start = event_time
        current_bucket_count = 1
        
    metrics["current_bucket_start"] = current_bucket_start
    metrics["current_bucket_count"] = current_bucket_count
    metrics["ewma"] = ewma
    metrics["mean"] = mean
    metrics["variance"] = variance
    metrics["m2"] = m2
    metrics["n_buckets"] = n_buckets
    
    # Calculate z-score
    std_dev = (variance) ** 0.5
    if std_dev > 0.0:
        z_score = (frequency - mean) / std_dev
    else:
        z_score = 0.0
        
    return metrics, float(frequency), rolling_rate, float(ewma), float(z_score)


def classify_severity(
    exception_type: str,
    environment: str,
    frequency: float,
    policy_rules: Dict[str, Any]
) -> str:
    """
    Classifies the severity of an incident based on exception type,
    environment, frequency, and configurable policy rules.
    """
    # 1. Check custom policy severity rules if available
    if policy_rules:
        type_map = policy_rules.get("exception_type_map", {})
        if exception_type in type_map:
            return type_map[exception_type]
            
        freq_thresholds = policy_rules.get("frequency_thresholds", {})
        if freq_thresholds:
            for lvl in [CRITICAL, HIGH, MEDIUM, LOW]:
                if lvl in freq_thresholds and frequency >= freq_thresholds[lvl]:
                    return lvl
                    
    # 2. Default severity rules
    severity = MEDIUM
    critical_exceptions = {"SystemError", "MemoryError", "OperationalError", "DatabaseError"}
    high_exceptions = {"ValueError", "KeyError", "TypeError", "ZeroDivisionError"}
    
    if exception_type in critical_exceptions:
        severity = CRITICAL
    elif exception_type in high_exceptions:
        severity = HIGH
    else:
        severity = MEDIUM
        
    # Promote severity in production environment
    if environment.lower() == "production":
        if severity == LOW:
            severity = MEDIUM
        elif severity == MEDIUM:
            severity = HIGH
        elif severity == HIGH:
            severity = CRITICAL
            
    # Upgrade severity if error frequency is extremely high
    if frequency >= 50:
        severity = CRITICAL
    elif frequency >= 20 and severity == MEDIUM:
        severity = HIGH
        
    return severity


def evaluate_anomaly(
    frequency: float,
    ewma: float,
    z_score: float,
    policy: Optional[models.ProjectPolicy]
) -> bool:
    """
    Evaluates whether the current metrics constitute an anomaly based on
    project policy thresholds (frequency, EWMA, z-score).
    """
    # Define fallback thresholds
    freq_th = 10
    z_th = 3.0
    ewma_th = 5.0
    
    if policy:
        freq_th = policy.anomaly_frequency_threshold
        z_th = policy.anomaly_zscore_threshold
        ewma_th = policy.anomaly_ewma_threshold
        
    if frequency >= freq_th:
        return True
    if ewma >= ewma_th:
        return True
    if z_score >= z_th:
        return True
        
    return False


async def process_event_pipeline(
    db: AsyncSession,
    event: schemas.EventCreate,
    project: models.Project
) -> models.Incident:
    """
    Executes the entire Ingestion Pipeline:
    Event -> Normalize -> Fingerprint -> Deduplicate -> Aggregate -> Severity -> Anomaly Evaluation -> Incident
    """
    # 1. Normalize
    env = event.environment or "production"
    stack_trace_str = event.stack_trace
    stack_frames = parse_stack_trace(stack_trace_str)
    
    # Resolve affected repository & project details
    affected_repository = project.repository
    affected_project = project.id
    
    # Extract metadata details
    context_data = {
        "file": event.file,
        "line": event.line,
        "function": event.function,
        "git_commit": event.git_commit,
        "runtime_metadata": event.runtime_metadata,
        "request_metadata": event.request_metadata,
        "sdk_version": event.sdk_version
    }
    
    # 2. Fingerprint
    fingerprint = generate_fingerprint(event.exception_type, event.exception_message, stack_frames)
    
    # 3. Deduplicate (Idempotency check)
    if event.event_id:
        res = await db.execute(select(models.ProcessedEvent).where(models.ProcessedEvent.event_id == event.event_id))
        processed = res.scalar_one_or_none()
        if processed:
            logger.info(f"Duplicate event delivery suppressed for event_id: {event.event_id}")
            # Fetch and return the existing incident associated with this processed event
            inc_res = await db.execute(select(models.Incident).where(models.Incident.id == processed.incident_id))
            return inc_res.scalar_one()

    # Find active incident for the fingerprint (not in terminal state)
    terminal_states = {MERGED, VERIFIED, REJECTED, REVERTED}
    res = await db.execute(
        select(models.Incident)
        .where(models.Incident.project_id == project.id)
        .where(models.Incident.fingerprint == fingerprint)
        .where(models.Incident.status.notin_(terminal_states))
    )
    incident = res.scalar_one_or_none()
    
    # Fetch Project Policy
    policy_res = await db.execute(
        select(models.ProjectPolicy)
        .where(models.ProjectPolicy.project_id == project.id)
    )
    policy = policy_res.scalar_one_or_none()
    policy_rules = policy.severity_rules if policy else {}

    now_dt = datetime.now(timezone.utc)
    event_time = now_dt.timestamp()
    
    is_new = False
    if not incident:
        # Create a new active incident
        is_new = True
        incident_id = f"inc_{uuid.uuid4().hex[:8]}"
        incident = models.Incident(
            id=incident_id,
            organization_id=project.organization_id,
            project_id=project.id,
            exception_type=event.exception_type,
            exception_message=event.exception_message,
            stack_trace=stack_trace_str,
            status=DETECTED,
            fingerprint=fingerprint,
            context=context_data,
            occurrence_count=0, # Will be set to 1 in aggregate
            first_seen=now_dt,
            last_seen=now_dt,
            environment=env,
            affected_repository=affected_repository,
            affected_project=affected_project,
            stack_frames={"frames": stack_frames},
            rolling_metrics={}
        )
        db.add(incident)
        logger.info(f"New incident created for fingerprint {fingerprint}: {incident_id}")

    # 4. Aggregate
    incident.occurrence_count += 1
    incident.last_seen = now_dt
    
    # Update rolling metrics
    metrics, freq, rate, ewma, z_score = update_rolling_metrics(incident.rolling_metrics, event_time)
    incident.rolling_metrics = metrics
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(incident, "rolling_metrics")
    incident.error_rate = rate

    # 5. Severity
    severity = classify_severity(event.exception_type, env, freq, policy_rules)
    incident.severity = severity

    # 6. Anomaly Evaluation
    is_anomaly = evaluate_anomaly(freq, ewma, z_score, policy)
    incident.is_anomaly = is_anomaly
    
    # Write ProcessedEvent for idempotency
    if event.event_id:
        processed_event = models.ProcessedEvent(
            event_id=event.event_id,
            incident_id=incident.id,
            created_at=now_dt
        )
        db.add(processed_event)

    # 7. Actionability & Incident state logging
    # Transition to DETECTED if newly created, otherwise log transition if severity/anomaly changes
    if is_new:
        # Write initial state transition
        history = models.IncidentHistory(
            id=f"hist_{uuid.uuid4().hex[:8]}",
            organization_id=incident.organization_id,
            incident_id=incident.id,
            from_state=None,
            to_state=DETECTED,
            timestamp=now_dt,
            reason="Incident detected by Ingestion Engine",
            metadata_info={"metrics": {"frequency": freq, "ewma": ewma, "z_score": z_score}}
        )
        db.add(history)

    # Determine actionability
    is_actionable = (severity in {HIGH, CRITICAL}) or is_anomaly
    if env.lower() == "development":
        is_actionable = False

        
    await db.commit()
    await db.refresh(incident)

    # Trigger Celery Worker task or background fallback if actionable and not enqueued yet
    bypass_celery = os.getenv("BYPASS_CELERY", "false").lower() == "true"
    if is_actionable and not incident.recovery_job_enqueued and not bypass_celery:

        incident.recovery_job_enqueued = True
        await db.commit()
        
        celery_sent = False
        try:
            celery_app.send_task(
                "tasks.run_recovery_pipeline",
                args=[incident.id, affected_repository, stack_trace_str]
            )
            logger.info(f"Enqueued recovery task via Celery for incident {incident.id}")
            celery_sent = True
        except Exception as e:
            logger.warning(f"Celery unavailable ({e}). Falling back to background thread recovery task for incident {incident.id}")

        if not celery_sent:
            try:
                import sys
                import importlib.util
                worker_tasks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../recovery-worker/tasks.py"))
                spec = importlib.util.spec_from_file_location("recovery_worker_tasks", worker_tasks_path)
                if spec and spec.loader:
                    recovery_worker_tasks = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(recovery_worker_tasks)
                    asyncio.create_task(asyncio.to_thread(
                        recovery_worker_tasks.run_recovery_pipeline.run,
                        incident.id, affected_repository, stack_trace_str
                    ))
                    logger.info(f"Successfully launched background thread recovery task for incident {incident.id}")
            except Exception as fallback_err:
                logger.error(f"Fallback background recovery task failed for incident {incident.id}: {fallback_err}", exc_info=True)
                
    return incident


