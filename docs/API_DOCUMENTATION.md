# API Reference & Data Contracts

This document specifies the REST API endpoints, request/response contracts, header authentication mechanisms, and real-time Server-Sent Events (SSE) supported by the **Overmend / Agent SDK** API service.

---

## 1. Authentication & Common Headers

All request endpoints enforce organizational context via HTTP headers or Bearer JWT tokens:

### Headers Format
```http
X-User-ID: usr_seed
X-User-Email: seed_user@example.com
X-Organization-ID: org_seed
Authorization: Bearer <jwt_token>
```

---

## 2. Telemetry & Incident Endpoints

### Ingest Telemetry Exception
* **Endpoint**: `POST /api/v1/incidents/telemetry`
* **Description**: Captures raw error tracebacks from runtime applications or the `@recover_on_exception` SDK.

#### Request Body
```json
{
  "service_name": "payments-service",
  "environment": "production",
  "exception_type": "ZeroDivisionError",
  "exception_message": "division by zero in calculate_fee",
  "stack_trace": "Traceback (most recent call last):\n  File \"payments.py\", line 14, in calculate_fee\n    rate = total / count\nZeroDivisionError: division by zero",
  "context_data": {
    "user_id": "usr_9921",
    "request_path": "/api/v1/checkout"
  }
}
```

#### Response (`201 Created`)
```json
{
  "incident_id": "inc_98f12a",
  "fingerprint": "a1b2c3d4e5f6...",
  "status": "TRIAGED",
  "severity": "HIGH",
  "duplicate": false
}
```

---

### List Incidents
* **Endpoint**: `GET /api/v1/incidents`
* **Query Parameters**: `status` (optional), `severity` (optional), `limit` (default: 50)
* **Response**: `200 OK` listing summary incident objects.

---

### Get Incident Details
* **Endpoint**: `GET /api/v1/incidents/{incident_id}`
* **Response (`200 OK`)**: Returns full incident record including stack trace frames, fault localization results, patch recommendations, and trust scores.

---

### Transition Incident State
* **Endpoint**: `POST /api/v1/incidents/{incident_id}/transition`
* **Request Body**:
```json
{
  "to_state": "HUMAN_REVIEW",
  "reason": "Manual override for production deployment"
}
```

---

## 3. Sandbox Real-Time Streaming (SSE)

### Stream Sandbox Test Output
* **Endpoint**: `GET /api/v1/sandbox/jobs/{job_id}/stream`
* **Media Type**: `text/event-stream`
* **Description**: Real-time event stream emitting build, sandbox execution, pytest results, and output logs.

#### Sample Event Stream Output
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"status": "CONTAINER_START", "details": "Initializing sandbox environment", "metadata": {"job_id": "job_88a1"}}

data: {"status": "RUNNING_TESTS", "details": "Running pytest test_payments.py", "metadata": {"passed": 4, "failed": 0}}

data: {"status": "COMPLETED", "details": "Sandbox test run finished with status 0", "metadata": {"execution_time_ms": 1420}}
```

---

## 4. Trust Engine Endpoints

### Evaluate Patch Trust Score
* **Endpoint**: `POST /api/v1/trust/evaluate`
* **Request Body**:
```json
{
  "patch_text": "--- a/payments.py\n+++ b/payments.py\n@@ -14,1 +14,3 @@\n-    rate = total / count\n+    if count == 0:\n+        return 0.0\n+    rate = total / count",
  "test_pass_result": true,
  "mutation_score": 0.92,
  "patch_locality": 1.0,
  "patch_size": 4,
  "files_changed": 1,
  "sensitive_file_flag": false,
  "blast_radius": 0.05
}
```

#### Response (`200 OK`)
```json
{
  "score": 0.91,
  "recommendation": "AUTO_MERGE",
  "risk_flags": [],
  "evidence": {
    "metric_scores": {
      "test_pass_score": 1.0,
      "mutation_score": 0.92,
      "patch_locality_score": 1.0,
      "patch_size_score": 1.0,
      "files_changed_score": 1.0,
      "historical_success": 1.0
    }
  }
}
```
