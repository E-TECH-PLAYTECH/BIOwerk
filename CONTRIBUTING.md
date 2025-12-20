# Contributing to BIOwerk

Thank you for investing in BIOwerk. This guide keeps contributions production-grade: fast local setup, repeatable quality gates, and predictable review/merge hygiene.

## Table of Contents
- [Development Setup](#development-setup)
- [Quality Gates (Format, Lint, Type, Security, Test)](#quality-gates-format-lint-type-security-test)
- [Branching and Pull Requests](#branching-and-pull-requests)
- [Commit Messages and Sign-offs](#commit-messages-and-sign-offs)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Plugins and Extensions](#plugins-and-extensions)
- [Code Style Guidelines](#code-style-guidelines)
- [Additional Resources](#additional-resources)

## Development Setup

### Prerequisites
- Python 3.10+
- Docker + Docker Compose
- Git
- Make (recommended for the provided task shortcuts)

### First-time bootstrap
1. **Clone and enter the repo**
   ```bash
git clone <repository-url>
cd BIOwerk
```
2. **Create a virtual environment and install dev dependencies**
   ```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make install-dev           # installs requirements-dev.txt and pre-commit
```
3. **Configure environment variables**
   ```bash
cp .env.example .env
# customize credentials/secrets before running services
```
4. **Bring up backing services (Postgres/Redis/etc.)**
   ```bash
make docker-up
```

## Quality Gates (Format, Lint, Type, Security, Test)
Every change must pass the following checks locally before review:

| Category   | Tools                                     | Command                  |
|------------|--------------------------------------------|--------------------------|
| Formatting | Black, isort                              | `make format`            |
| Linting    | Flake8, Pylint                            | `make lint`              |
| Typing     | mypy                                      | `make type-check`        |
| Security   | Bandit, Safety, detect-secrets            | `make security`          |
| Tests      | pytest (unit/integration/e2e as needed)   | `make test` or targeted  |

For a complete sweep, run `make check-all` (formats, lints, types, security, tests with coverage). Do not open a PR until these checks succeed locally.

## Branching and Pull Requests
- **Branch naming:** `feature/<area>-<slug>`, `fix/<area>-<issue>`, or `chore/<area>-<task>` (examples: `feature/mesh-routing`, `fix/auth-token-refresh`).
- **PR titles:** Use Conventional Commit style (e.g., `docs: refine contributing guide`).
- **PR description:** Include a crisp summary, testing evidence, risk/rollback notes, and linked issues. Attach screenshots for UI changes.
- **Review readiness:** All checklists in this document must be satisfied (tests, docs updated, backward compatibility noted). CI failures must be resolved before requesting review.
- **Breaking changes:** Call out migrations, config flags, and rollout steps explicitly; provide a rollback strategy in the PR body.

## Commit Messages and Sign-offs
- **Conventional Commits** are required: `<type>(<scope>): <subject>` with optional body/footer. Types include `feat`, `fix`, `docs`, `refactor`, `chore`, `test`, `perf`, `security`, `style`.
- **DCO/Sign-off:** Every commit must include a Signed-off-by trailer. Use `git commit -s` or add `Signed-off-by: Full Name <email@example.com>` manually. Commits lacking sign-off will be rejected.
- **Content expectations:**
  - Summarize *what* and *why*; reference issue IDs when applicable.
  - Do not hide breaking changes—surface them in both commit body and PR.
  - Squash noisy WIP commits before opening the PR.

## Development Workflow
1. Start from `main` and create a feature branch: `git checkout -b feature/<slug>`.
2. Implement the change with tests alongside code. Keep functions small and typed.
3. Run `make check-all`; fix any findings.
4. Stage and commit with `git commit -s -m "<type>(<scope>): <subject>"`.
5. Push and open a PR with the checklist completed and relevant documentation updates attached.

### Pre-commit Hooks
Hooks install automatically via `make install-dev`. Run them anytime with:
```bash
make pre-commit
# or
pre-commit run --all-files
```

### Common Tasks
- **Run services locally:** `make run-mesh` or `make run-service SERVICE=synapse`
- **Database migrations:**
  ```bash
  make migrations-create MSG="add users table"
  make migrations-upgrade
  make migrations-downgrade
  ```
- **Export OpenAPI snapshots:** `python scripts/export_openapi_snapshots.py`

## Testing
- Test layout:
  - `tests/` for unit tests
  - `tests/e2e/` for end-to-end flows
  - Shared fixtures in `tests/conftest.py`
- Use `pytest` with `pytest-asyncio` for async paths. Target >80% coverage for new code.
- Apply markers: `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.security`.
- Examples live in `examples/demo_requests.json` and `examples/run_demo_requests.py` for exercising mesh requests.

## Plugins and Extensions
- BIOwerk supports a modular plugin/extension model. Start with the [Plugin & Extension Architecture guide](docs/PLUGIN_EXTENSION_ARCHITECTURE.md) for message envelopes, mesh registration, and shared utilities.
- Keep plugins stateless where possible, declare targeted mesh API versions, and wire into RBAC/audit controls. See the checklist in that guide before opening a PR.

## Code Style Guidelines
- Python: PEP 8 with 120-character lines, full type hints, and Google-style docstrings for public functions/classes.
- Keep functions focused, avoid large parameter lists, and favor pure helpers. Handle errors explicitly—never swallow exceptions.
- Security posture: validate inputs (see `matrix.api_models`), fail closed, and prefer immutability for payloads.

## Additional Resources
- [OpenAPI Snapshots & Try-It Examples](docs/OPENAPI_AND_TRY_IT.md)
- [Load & Chaos Testing Playbook](docs/LOAD_AND_CHAOS_TESTING.md)
- [API Rate-Limit Testing Guide](docs/API_RATE_LIMIT_TESTING.md)
- [Security Guide](docs/SECURITY.md)
- [Monitoring and Alerting](docs/MONITORING_AND_ALERTING.md)
- [Installation and Operations](docs/INSTALLATION_AND_OPERATIONS.md)
