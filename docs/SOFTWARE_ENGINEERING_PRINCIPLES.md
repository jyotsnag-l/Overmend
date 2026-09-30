# Standard Software Engineering Principles

This document outlines the standard software engineering principles and architectural patterns implemented across the **Overmend / Agent SDK** codebase.

---

## 1. SOLID Design Principles

### Single Responsibility Principle (SRP)
Each package and component in the workspace handles a distinct domain responsibility:
- [`packages/fault-localizer`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/packages/fault-localizer): Exclusively handles stack trace parsing, AST static analysis, and Git blame correlation.
- [`packages/patch-engine`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/packages/patch-engine): Focuses purely on diff parsing (`unidiff`), path safety verification, and dry-run syntax checking.
- [`packages/trust-engine-core`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/packages/trust-engine-core): Evaluates AST code mutations and computes deterministic trust scoring formulas.
- [`packages/sandbox-manager`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/packages/sandbox-manager): Manages container execution, process isolation, and log streaming.

### Open/Closed Principle (OCP)
Core modules are open for extension but closed for modification:
- **Authentication Providers**: [`AuthProvider`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/apps/api/auth/provider.py#L27) defines an abstract interface. Subclasses like `JWTAuthProvider` and `HeaderAuthProvider` add new auth mechanisms without modifying the API core router.
- **Patch Providers**: Pluggable LLM/Rule provider interfaces allow adding new patch models (Anthropic, OpenAI, local models) seamlessly.

### Liskov Substitution Principle (LSP)
All auth providers inherit from [`AuthProvider`](file:///c:/Users/sreej/OneDrive/Desktop/agent_sdk/apps/api/auth/provider.py#L27) and adhere strictly to `async authenticate(request: Request) -> Optional[UserPrincipal]`, guaranteeing plug-and-play substitution in FastAPI dependency injection.

### Interface Segregation Principle (ISP)
Clients consume minimal, highly focused interfaces. For instance, `RepositoryAccess` exposes read-only methods (`read_file`, `get_blame`, `get_recent_commits`) without polluting the fault localization engine with write or deployment logic.

### Dependency Inversion Principle (DIP)
High-level pipeline workflows depend on abstract abstractions rather than low-level infrastructure implementations. FastAPI routes depend on injected session factories (`get_db`) and strategy interfaces rather than raw singletons.

---

## 2. Deterministic Trust & Defense-in-Depth

AI-generated code fixes cannot be trusted implicitly. The platform applies a multi-layered verification strategy:

1. **Syntactical Validation**: Dry-running diffs in memory using `ast.parse()` to prevent invalid Python code from reaching execution.
2. **AST Mutation Testing**: Generating synthetic mutants (`ast.NodeTransformer`) across operators (`==`, `!=`, `<`, `and`/`or`) to calculate a quantitative `mutation_score`.
3. **Deterministic Scoring Model**: Calculating a normalized score $S \in [0, 1]$ via weighted metric evaluation:
   $$S = \text{TestPass}(0.40) + \text{MutationScore}(0.30) + \text{Locality}(0.10) + \text{PatchSize}(0.10) + \text{FilesChanged}(0.05) + \text{History}(0.05) - \text{Penalties}$$
4. **Gradated Triage Thresholds**:
   - $S \ge 0.85$: `AUTO_MERGE`
   - $S \ge 0.50$: `HUMAN_REVIEW`
   - $S < 0.50$ or failed tests: `REJECT`

---

## 3. Idempotency & State Machine Integrity

To ensure reliability during concurrent worker execution and Celery retries, incident state transitions are strictly governed:

- **Enforced Lifecycle**: `DETECTED` $\rightarrow$ `TRIAGED` $\rightarrow$ `LOCALIZED` $\rightarrow$ `PATCH_GENERATED` $\rightarrow$ `SANDBOX_RUNNING` $\rightarrow$ `TESTED` $\rightarrow$ `TRUST_EVALUATED` $\rightarrow$ `AUTO_MERGE` / `HUMAN_REVIEW` $\rightarrow$ `VERIFIED`.
- **Atomic Transitions & Audit Trails**: Every state change writes immutable records to `IncidentHistory` and `AuditLog` within the same database transaction.
- **Deduplication Fingerprinting**: Fingerprinting error tracebacks via MD5 (`generate_fingerprint`) prevents redundant incident loops for identical root causes.

---

## 4. Zero-Trust Sandboxing & Defensive Security

- **Path Traversal Defense**: Diff validation verifies that all file targets reside within `os.path.abspath(repo_path)` to prevent directory traversal attacks (`../../etc/passwd`).
- **Process Isolation**: Code patches are executed inside isolated sandboxes with strict execution timeouts and restricted filesystem privileges.
- **Asymmetric Token Signing**: GitHub App integration utilizes RS256 private key signature algorithms to request short-lived installation access tokens.

---

## 5. Algorithmic Rigor & Clean Telemetry

- **Online Incremental Statistics (Welford's Algorithm)**: Calculates running mean and variance without storing raw telemetry arrays.
- **Spike Anomaly Detection (EWMA & Z-Scores)**: Uses exponentially weighted moving averages to track error frequencies over 60-second sliding windows.
- **Reverse-Order Hunk Patching**: Sorts diff hunks in reverse order of line start offsets (`key=lambda h: h.source_start, reverse=True`) to eliminate line offset drift during patching.
