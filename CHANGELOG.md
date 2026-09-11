# Changelog

All notable changes to `createos-sandbox` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## Deprecation policy

- Anything re-exported from `src/createos/__init__.py` is part of the public
  API.
- We are pre-1.0, so the API is allowed to break in MINOR bumps — breaking
  changes ship as MINOR, and PATCH releases are bug-fix only.
- Where possible, breaking changes are announced one minor before removal: the
  old surface keeps working, gains a `DeprecationWarning`, and this file points
  at the replacement.

## [Unreleased]

## [0.1.0] — 2026-09-11

Initial release.

- `Client` with sandbox lifecycle (create, pause, resume, fork, destroy),
  command execution and NDJSON streaming, file transfer and snapshots,
  managed processes, networks, ingress previews, and custom templates.
- Typed wire-contract models, typed errors, and `py.typed`.

[Unreleased]: https://github.com/NodeOps-app/createos-python-sdk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/NodeOps-app/createos-python-sdk/releases/tag/v0.1.0
