#!/usr/bin/env bash
# Release gate + tag. `./scripts/publish.sh` tags and pushes v<version>,
# which triggers .github/workflows/ci.yml to build and publish to PyPI.
# `./scripts/publish.sh --dry` stops after building and checking.
set -euo pipefail
cd "$(dirname "$0")/.."

py="$PWD/.venv/bin/python"
[ -x "$py" ] || py="$(command -v python || command -v python3)"

"$py" -m pytest -q
"$py" -m ruff format --check src tests examples
"$py" -m ruff check src tests examples
"$py" -m mypy src/createos --ignore-missing-imports

rm -rf dist
"$py" -m build
"$py" -m twine check --strict dist/*

version=$("$py" -c "import re,pathlib;print(re.search(r'\"(.+)\"',pathlib.Path('src/createos/_version.py').read_text()).group(1))")

if [ "${1:-}" = "--dry" ]; then
  echo "dry run OK — would tag and push v$version, triggering the PyPI release"
  exit 0
fi

read -r -p "tag and push v$version to trigger the PyPI release? [y/N] " reply
[ "$reply" = "y" ] || exit 1
git tag "v$version" && git push origin "v$version"
