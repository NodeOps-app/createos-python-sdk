# CLAUDE.md

Agent guide for the **CreateOS Python SDK**. Contributor conventions live in
[`CONTRIBUTING.md`](CONTRIBUTING.md); this file covers what an agent needs that
the contributor guide does not.

## This repository

- Package: `createos-sandbox` on PyPI, imported as `createos`.
- Source: `src/createos/`. Public surface is everything re-exported from
  `src/createos/__init__.py`.
- Python 3.10–3.14. Keep the 3.10 floor: `from __future__ import annotations`
  in every module, and the local `StrEnum` shim in `models.py` instead of the
  stdlib 3.11 one.
- Local checks: `.venv/bin/ruff format --check src tests examples`,
  `.venv/bin/ruff check src tests examples`,
  `.venv/bin/mypy src/createos --ignore-missing-imports`,
  `.venv/bin/pytest --cov=createos --cov-fail-under=70`.
- Release: `./scripts/publish.sh` (see CONTRIBUTING.md → Releasing).

## The CreateOS SDK family

This is one of three clients for the **same** CreateOS Sandbox API. They are
separate repositories that are expected to stay behaviourally in sync. A change
worth making here is usually worth making in the siblings.

| Language | Repository | Package | Agent guide | Local sibling |
| --- | --- | --- | --- | --- |
| TypeScript | [createos-sandbox-sdk](https://github.com/NodeOps-app/createos-sandbox-sdk) | `@nodeops-createos/sandbox` | [`CLAUDE.md`](https://github.com/NodeOps-app/createos-sandbox-sdk/blob/main/CLAUDE.md) → [`AGENTS.md`](https://github.com/NodeOps-app/createos-sandbox-sdk/blob/main/AGENTS.md) | `../fc-sdk` |
| Go | [createos-go-sdk](https://github.com/NodeOps-app/createos-go-sdk) | `github.com/NodeOps-app/createos-go-sdk` | [`CLAUDE.md`](https://github.com/NodeOps-app/createos-go-sdk/blob/main/CLAUDE.md) | `../createos-go-sdk` |
| Python | this repo | `createos-sandbox` | this file | — |

Upstream of all three:

- **Service** — `../fc` (`nodeops-app/fc`). Source of truth for the wire
  contract: `openapi.yaml`, plus `CLAUDE.md` / `AGENT.md` for its own rules.
  If the SDKs disagree about what the API does, the service wins.
- **Public docs** — `../createos-v2-landing/apps/docs/src/pages/Sandbox/`,
  published at <https://createos.sh/docs/Sandbox>. Every language snippet lives
  in `SDK/Overview.mdx` inside a `:::code-group`, one fenced block per language
  (` ```python [Python] `). A new SDK capability that users should see is not
  shipped until that page has it. The older `website-04` checkout is retired;
  do not edit it.

## Cross-SDK parity protocol

Run this before you call any change to this repo done. It is a read-and-report
protocol — **do not edit a sibling repository unless the user asks you to.**

1. **Classify the change.**
   - *Wire contract* (new endpoint, changed field, new request/response shape)
     → affects all three SDKs and usually the docs.
   - *Behaviour* (retry policy, timeout default, stream framing, error
     mapping) → affects all three SDKs.
   - *Bug fix* → check whether the siblings have the same bug. They were
     written from the same spec, so they usually do.
   - *Ergonomics* (a Pythonic helper, a context manager) → often has a natural
     equivalent in the siblings; propose it, don't assume it.
   - *Repo-local* (packaging, lint config, CI) → no parity obligation.
2. **Check the siblings.** Read the matching file under `../fc-sdk/src/` and
   `../createos-go-sdk/sandbox/`. If a sibling checkout is missing, say so
   rather than guessing.
3. **Report.** End the task with a short parity note: what ports to which SDK,
   what does not, and why. Name the file the sibling change would land in.
4. **Docs.** If the change adds or alters a user-visible capability, say
   whether `SDK/Overview.mdx` and the affected page under
   `apps/docs/src/pages/Sandbox/` need updating.

The same protocol runs in reverse: when the TypeScript or Go SDK gains a
feature or fix, check whether it belongs here.

### Current parity baseline

The Python and Go SDKs expose the same surface and ship the same nine examples
(`hello_world`, `command_streaming`, `files_and_snapshots`, `ingress_preview`,
`managed_process`, `network`, `custom_template`, `desktop`,
`execution_server`). The TypeScript SDK has the same core surface plus a much
larger integration-example corpus. Treat a gap against Go as a real gap; treat
a gap against a TypeScript *integration example* as optional.
