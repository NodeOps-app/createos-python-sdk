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
