# Contributing

Thank you for contributing to the CreateOS Python SDK.

## Setup

Create a virtual environment and install the SDK with its development tools:

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Run the complete local check suite:

```sh
.venv/bin/ruff format --check src tests examples
.venv/bin/ruff check src tests examples
.venv/bin/mypy src/createos --ignore-missing-imports
.venv/bin/pytest --cov=createos --cov-fail-under=70
```

## Commit convention

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<optional-scope>): <subject>
```

Accepted types are `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`,
and `perf`. Write the subject in imperative mood, keep it at 50 characters or
fewer, start it with a lowercase letter, and do not end it with a period.

Examples:

```text
feat(sandbox): add disk attachment
fix(transport): honor retry-after header
docs(readme): add network example
test(processes): cover output replay
chore: prepare v0.1.0 release
```

For an incompatible public API change, add `!` before the colon and explain the
change in a `BREAKING CHANGE:` commit footer:

```text
feat(sandbox)!: change create response
```

## Before opening a pull request

Run the complete local check suite. Add or update tests for behavior changes,
and update public docstrings and README examples when the public API changes.

## Releasing

The package `createos-sandbox` is published to PyPI by CI. Pushing a
`v<version>` tag runs `.github/workflows/ci.yml`, which builds the sdist and
wheel and uploads them via PyPI Trusted Publishing (OIDC — no token stored
anywhere).

1. Bump `__version__` in `src/createos/_version.py` (the single source of
   truth — `pyproject.toml` reads it) and move the `CHANGELOG.md`
   `[Unreleased]` entries under the new version.
2. Dry run the release gate: `./scripts/publish.sh --dry`.
3. Release: `./scripts/publish.sh`. It reruns tests, lint, types, builds and
   checks the sdist/wheel, then tags and pushes `v<version>` — CI takes it
   from there.

One-time setup: on PyPI, add this repo as a trusted publisher for
`createos-sandbox` (Your projects → createos-sandbox → Publishing → Add a
new publisher), with workflow name `ci.yml` and environment name `pypi`.
