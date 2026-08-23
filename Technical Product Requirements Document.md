## Technical Product Requirements Document

## SUMMARY

Build a multi-tenant cloud platform that provides: Application Monitoring, Autonomous Fault Localization, AI Patch Generation, Isolated Patch Execution, Mutation-Based Trust Evaluation, Policy-Based Deployment Decisions, and

GitHub Automation. The system must support the Recovery Pipeline independently from the Trust Engine.

## RECOMMENDED TECHNOLOGY STACK

Frontend: React + TypeScript + Vite UI: Tailwind CSS Backend API: FastAPI Primary language: Python Job queue: Celery Queue/broker: Redis Database: PostgreSQL Vector search: pgvector AI: OpenAI API / Anthropic API abstraction SDK: Python Static analysis: Python AST Git analysis: GitPython Diff parsing: unidiff Sandbox: Docker Mutation testing: mutmut initially GitHub integration: GitHub App + REST API Object storage: S3-compatible storage / Cloudflare R2 Authentication: Auth provider or managed authentication layer Deployment: Docker Observability: OpenTelemetry + structured logging Testing: pytest Frontend tests: Vitest + Playwright API schema:

OpenAPI

## ARCHITECTURE

Use a control-plane / worker-plane architecture with Load Balancer, React Frontend, FastAPI API Gateway, PostgreSQL, Redis, Celery Workers, Recovery Worker, Trust Worker, Sandbox Manager, Docker Sandboxes, GitHub

App, and Storage.

## SERVICE BOUNDARIES

API Service: Authentication, Authorization, CRUD operations, Dashboard APIs, Incident APIs, Project APIs, Configuration, Job creation, Webhook receiving. Must not directly perform long-running patch execution. Monitoring Ingestion Service: Receive SDK events, Validate payload, Authenticate project, Fingerprint stack traces, Deduplicate incidents, Store events, Trigger anomaly evaluation. Recovery Worker: Fetch incident, Locate fault, Retrieve repository, Retrieve historical context, Generate patch candidates, Validate diffs, Submit sandbox jobs. Sandbox Worker: Create ephemeral workspace, Clone repository, Apply patch, Install environment, Execute tests, Capture logs, Enforce resource limits, Destroy environment. Trust Worker: Create mutants, Execute mutant test runs, Calculate mutation score, Aggregate evidence, Generate confidence, Return recommendation. GitHub Worker: Create branch,

Push changes, Create PR, Update PR, Monitor CI, Merge where allowed.

## PRODUCT BOUNDARIES

Recovery Platform: Monitoring, Diagnosis, Patch Generation, Sandbox, GitHub. Trust Engine: Patch -> Tests -> Mutations -> Evidence -> Trust Score. The Trust Engine must be independently callable.

## FINAL PRODUCT DEFINITION

Three products working together: Product 1 — Recovery Cloud: Detects and autonomously repairs software failures. Product 2 — Sandbox Cloud: Safely executes arbitrary candidate patches in disposable environments. Product 3 — Trust Engine: Determines how much confidence should be placed in an AI-generated software patch. Together: An autonomous software recovery PaaS with an independent patch trust layer.
