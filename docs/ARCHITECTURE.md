# System Architecture & Design

This document details the high-level architecture, component design, data flows, and state machine of the **Overmend / Agent SDK** platform.

---

## 1. System Overview & Architecture Diagram

Overmend operates as a microservices system composed of an API server, asynchronous Celery workers, domain core packages, and a React web dashboard.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client / SDK Layer                            │
│  ┌─────────────────────────┐              ┌──────────────────────────┐  │
│  │   Recovery Python SDK   │              │   React / Vite Dashboard │  │
│  │ (@recover_on_exception) │              │    (Incident Lifecycle)  │  │
│  └────────────┬────────────┘              └─────────────┬────────────┘  │
└───────────────┼─────────────────────────────────────────┼───────────────┘
                │ HTTP POST /telemetry                    │ HTTP / SSE
┌───────────────▼─────────────────────────────────────────▼───────────────┐
│                            FastAPI Backend                              │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ API Endpoints (/incidents, /trust, /sandbox, /auth)               │  │
│  │ Deduplication Fingerprinting (MD5) & Welford Anomaly Detection    │  │
│  └──────────────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────┘
                                      │ Enqueue Tasks
┌─────────────────────────────────────▼───────────────────────────────────┐
│                        Asynchronous Celery Workers                      │
│  ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐  │
│  │     GitHub Worker     │ │  Recovery Worker  │ │  Sandbox Worker   │  │
│  │ (Webhooks & PR Merge) │ │ (Fault Localize)  │ │ (Test Execution)  │  │
│  └───────────────────────┘ └───────────────────┘ └───────────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │ Invokes Core Packages
┌─────────────────────────────────────▼───────────────────────────────────┐
│                             Core Domain Engines                         │
│  ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐  │
│  │    Fault Localizer    │ │   Patch Engine    │ │   Trust Engine    │  │
│  │  (AST & Stack Trace)  │ │  (Diff & Policy)  │ │ (Mutation & Score)│  │
│  └───────────────────────┘ └───────────────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Microservice & Package Breakdown

### Services (`apps/`)

* **`apps/api`**: FastAPI server handling REST requests, auth verification, telemetry ingestion, error rate anomaly detection, and SSE streaming.
* **`apps/github-worker`**: Celery worker listening for GitHub webhook events, branch creation, and PR management.
* **`apps/recovery-worker`**: Autonomous recovery coordinator running stack trace resolution and candidate patch generation.
* **`apps/sandbox-worker`**: Sandbox execution daemon running test suites inside isolated containers.
* **`apps/trust-engine`**: Trust evaluation engine executing AST mutations and scoring patch safety.

### Packages (`packages/`)

* **`packages/fault-localizer`**: Stack trace parsing, AST static analysis (`NodeVisitor`), line range resolution, git blame attribution.
* **`packages/patch-engine`**: Unified diff validation, path safety verification (`abspath`), dry-run AST syntax checking.
* **`packages/trust-engine-core`**: Mutation testing (`ast.NodeTransformer`), score formulas, rule-based recommendation.
* **`packages/sandbox-manager`**: Container environment provisioning, test command execution, log streaming.
* **`packages/github-client`**: RS256 JWT auth signing and GitHub REST API client wrapper.
* **`packages/recovery-sdk`**: Python SDK decorator (`@recover_on_exception`) for automatic error capture and reporting.

---

## 3. Incident State Machine Flow

```
[ Telemetry Received ]
          │
          ▼
     (DETECTED) ────► [ Fingerprinting & Welford Anomaly Check ]
          │
          ▼
      (TRIAGED) ────► [ AST Localizer & Git Blame ]
          │
          ▼
     (LOCALIZED) ───► [ LLM / Rule Patch Generation ]
          │
          ▼
  (PATCH_GENERATED) ─► [ In-Memory Dry Run Syntax Check ]
          │
          ▼
  (SANDBOX_RUNNING) ─► [ Isolated Pytest Execution & Log Stream ]
          │
          ▼
       (TESTED) ────► [ AST Mutation Testing & Trust Scorer ]
          │
          ▼
  (TRUST_EVALUATED)
      │        │
      │        └──────────────────────┐
      │ (Score >= 0.85)               │ (Score < 0.85)
      ▼                               ▼
 (AUTO_MERGE)                  (HUMAN_REVIEW)
      │                               │
      ▼                               ▼
  (MERGED)                        (VERIFIED)
```

---

## 4. Database Schema & Data Models

Managed via SQLAlchemy Async ORM (`apps/api/models.py`):

* **`Organization`**: Workspace tenant configuration and policy overrides.
* **`Repository`**: Connected GitHub repositories and environment metadata.
* **`Incident`**: Incident status, exception metadata, stack trace, fingerprint hash, assigned severity, and final score.
* **`Patch`**: Unified diff content, patch provider info, test run outputs, mutation metrics, and decision rationale.
* **`IncidentHistory`**: Immutable log of lifecycle transitions.
* **`AuditLog`**: Compliance audit records detailing user/system actions.
