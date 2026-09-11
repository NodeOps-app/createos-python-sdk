#!/usr/bin/env bash
# Release gate + upload. `./scripts/publish.sh` uploads to PyPI;
# `./scripts/publish.sh --dry` stops after building and checking.
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pytest -q
python -m ruff format --check src tests examples
python -m ruff check src tests examples
python -m mypy src/createos --ignore-missing-imports

rm -rf dist
python -m build
python -m twine check --strict dist/*

version=$(python -c "import re,pathlib;print(re.search(r'\"(.+)\"',pathlib.Path('src/createos/_version.py').read_text()).group(1))")

if [ "${1:-}" = "--dry" ]; then
  echo "dry run OK — would publish createos-sandbox $version"
  exit 0
fi

read -r -p "publish createos-sandbox $version to PyPI? [y/N] " reply
[ "$reply" = "y" ] || exit 1
python -m twine upload dist/*
git tag "v$version" && git push origin "v$version"
