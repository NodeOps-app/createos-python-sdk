# Changelog

All notable changes to `createos-sandbox` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## Deprecation policy

- Anything re-exported from `src/createos/__init__.py` is part of the public
  API.
- We are pre-1.0, so the API is allowed to break in MINOR bumps. PATCH releases
  normally contain bug fixes; 0.1.2 also changes the API key environment
  variable.
- Where possible, breaking changes are announced one minor before removal: the
  old surface keeps working, gains a `DeprecationWarning`, and this file points
  at the replacement.

## [Unreleased]

### Added

- Sandbox access token creation, inspection, rotation, disabling, and a
  separate delegated credential handle.

### Fixed

- Remove credentials inherited from supplied HTTP clients on public requests.
- Bound error-response inspection to 4 MiB before buffering the response.

## [0.1.2] — 2026-09-16

### Changed

- `Client()` now reads its default API key from `CREATEOS_API_KEY`. Update
  environments that rely on the previous variable name.

## [0.1.1] — 2026-09-11

### Added

- Optional per-operation timeouts for file uploads and downloads.

### Fixed

- Repository-only artwork is excluded from source distributions.

## [0.1.0] — 2026-09-11

Initial release.

- `Client` with sandbox lifecycle (create, pause, resume, fork, destroy),
  command execution and NDJSON streaming, file transfer and snapshots,
  managed processes, networks, ingress previews, and custom templates.
- Typed wire-contract models, typed errors, and `py.typed`.

[Unreleased]: https://github.com/NodeOps-app/createos-python-sdk/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/NodeOps-app/createos-python-sdk/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/NodeOps-app/createos-python-sdk/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/NodeOps-app/createos-python-sdk/releases/tag/v0.1.0
