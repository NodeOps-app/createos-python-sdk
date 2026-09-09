"""Operations a sandbox can request for its own lifecycle."""

from __future__ import annotations

import httpx


def _signal(action: str, reason: str = "", *, timeout: float = 10.0) -> None:
    response = httpx.post(
        f"http://127.0.0.1:1029/self/{action}",
        params={"reason": reason} if reason else None,
        timeout=timeout,
    )
    if response.status_code != 202:
        raise RuntimeError(
            f"self-{action} request returned HTTP {response.status_code}"
        )


def self_pause(reason: str = "", *, timeout: float = 10.0) -> None:
    """Ask the local sandbox agent to pause this sandbox."""
    _signal("pause", reason, timeout=timeout)


def self_delete(reason: str = "", *, timeout: float = 10.0) -> None:
    """Ask the local sandbox agent to irreversibly delete this sandbox."""
    _signal("delete", reason, timeout=timeout)
