# Contributing Guidelines

Thank you for contributing to **Overmend / Agent SDK**! We appreciate your support in building autonomous software recovery systems.

---

## 1. Code Standards & Style Guidelines

### Python
- **Format & Linting**: Follow PEP 8 guidelines. Type hints are mandatory across all public functions.
- **Docstrings**: Include clear Google-style docstrings for public classes and functions.
- **AST Safety**: When adding AST transformers or visitors, ensure proper handling of line number offsets and optional attributes (`end_lineno`).

### TypeScript / React
- Use strict TypeScript typing. Avoid `any` types.
- Components must be modular and styled using modern CSS tokens (`index.css`).

---

## 2. Pull Request Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/add-custom-localizer
   ```

2. **Run Tests Locally**:
   Ensure all pytest suites pass clean before pushing:
   ```powershell
   pytest tests/
   ```

3. **Commit Message Format**:
   Use semantic commit messages:
   - `feat(localizer): add AST control flow finder`
   - `fix(patch-engine): resolve hunk offset shift bug`
   - `docs(api): update SSE streaming specification`

4. **Submit PR**:
   Open a Pull Request against the `main` branch. Ensure code review approval and clean CI build checks.

---

## 3. Code Review & Quality Gates

Every Pull Request must pass the following automated quality checks:
- **Unit & Integration Tests**: 100% pass rate across `pytest tests/`.
- **Patch Engine Security Check**: Zero path traversal vulnerabilities or unauthorized file access.
- **AST Mutation Benchmark**: High mutation coverage ($\ge 80\%$) on core decision modules.
