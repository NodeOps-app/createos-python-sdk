"""Exception types raised by the CreateOS SDK."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class CreateOSError(Exception):
    """Base error raised by this SDK."""


class AuthenticationError(CreateOSError):
    """Authentication was required but no API key was configured."""


class OperationTimeout(CreateOSError, TimeoutError):
    """An SDK polling operation exhausted its time budget."""


class ProtocolError(CreateOSError):
    """The API returned a response that did not follow its wire contract."""


class CommandError(CreateOSError):
    """A shell command completed unsuccessfully."""

    def __init__(self, message: str, response: Any) -> None:
        super().__init__(message)
        self.response = response


class APIError(CreateOSError):
    """A non-successful HTTP response from the CreateOS API."""

    def __init__(
        self,
        *,
        status_code: int,
        method: str,
        endpoint: str,
        body: bytes,
        headers: Mapping[str, str],
    ) -> None:
        self.status_code = status_code
        self.method = method.upper()
        self.endpoint = endpoint
        self.body = body
        self.headers = dict(headers)
        self.request_id = headers.get(
            "x-request-id", headers.get("X-Request-ID", "")
        )
        self.code = 0
        message = "request failed"
        try:
            envelope = json.loads(body)
            self.code = int(envelope.get("code") or 0)
            message = (
                envelope.get("message")
                or _data_message(envelope.get("data"))
                or message
            )
        except (ValueError, TypeError, AttributeError):
            pass
        super().__init__(
            f"{self.method} {endpoint}: HTTP {status_code}: {message}"
        )


def _data_message(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return "; ".join(f"{key}: {data[key]}" for key in sorted(data))
    return ""
