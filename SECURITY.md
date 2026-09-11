# Security Policy

## Supported versions

Security fixes land on the latest minor release.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

The preferred channel is GitHub's private vulnerability reporting. On this
repository, open the **Security** tab, choose **Report a vulnerability**, and
file a private advisory. No email is required, and the report stays
confidential until a fix is published.

Please include enough detail to reproduce: affected version, Python version, a
minimal proof of concept, and the impact you observed.

We aim to acknowledge reports within **72 hours** and will keep you updated as
we investigate and prepare a fix. We will coordinate disclosure timing with you.

## Dependency attack surface

This SDK has a single runtime dependency, [`httpx`](https://www.python-httpx.org/).
Everything else (`pytest`, `ruff`, `mypy`, `build`, `twine`) is build-time only
and never ships to consumers.
