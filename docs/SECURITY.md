# Security Model & Vulnerability Policies

This document outlines the security architecture, threat model, authorization mechanisms, and defensive controls implemented across the **Overmend / Agent SDK** platform.

---

## 1. Zero-Trust Security Posture

Because Overmend automatically analyzes code and executes synthesized patches, security is designed around a **Zero-Trust** model:

1. **Untrusted Input Assumptions**: AI-generated code patches are treated as untrusted third-party code.
2. **Container Isolation**: Candidate patches are executed within ephemeral, resource-constrained sandboxes.
3. **Restricted File Access**: Patches cannot read or modify files outside the current target repository.

---

## 2. Path Traversal & File Boundary Defense

To prevent malicious patches or crafted stack traces from performing directory traversal attacks (e.g. `../../../../etc/passwd` or overwrite root files), the patch engine enforces strict path checks:

```python
# Absolute Path Resolution & Traversal Prevention
repo_abs_path = os.path.abspath(repo_path)
file_abs_path = os.path.abspath(os.path.join(repo_abs_path, file_path))

if not file_abs_path.startswith(repo_abs_path):
    raise SecurityError(f"Access denied: Path '{file_path}' attempts to traverse outside repository root.")
```

---

## 3. GitHub App Authentication & Cryptography

GitHub API interactions are authenticated using asymmetric **RS256 JWT Signing**:

- **Private Key Storage**: The private RSA key (`github-private-key.pem`) is kept strictly secret and never exposed to API endpoints or sandboxes.
- **Short-Lived Installation Tokens**: RS256 JWTs sign requests to obtain short-lived Installation Access Tokens (valid max 60 minutes) for repository actions.
- **Minimal Scope Tokens**: Tokens request scoped permission bounds (`contents: write`, `pull_requests: write`) restricted strictly to the target repository.

---

## 4. Sandbox Isolation & Resource Limits

* **No Dynamic System Capabilities**: Containers run with dropped Linux capabilities (`--cap-drop=ALL`).
* **Memory & CPU Limits**: Cgroups enforce hard boundaries on memory usage (e.g., max 512MB RAM) and CPU utilization to prevent DoS resource exhaustion.
* **Execution Timeout**: Sandbox test runs enforce a hard execution timeout (e.g., 30 seconds) to terminate infinite loops or hanging worker processes.

---

## 5. Security Vulnerability Reporting

If you discover a potential security flaw in this platform:
- Do **not** disclose it publicly or open public GitHub issues.
- Email the security team at `security@overmend.io` with full reproduction steps.
- Security disclosures are reviewed and addressed within 48 hours.
