from __future__ import annotations

import email.utils
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .errors import APIError, AuthenticationError, ProtocolError
from .models import Model, RequestOptions, RetryOptions


@dataclass(slots=True)
class RawResponse:
    response: httpx.Response

    def close(self) -> None:
        self.response.close()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class Transport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float,
        user_agent: str,
        retry: RetryOptions,
        http_client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(base_url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base URL scheme must be http or https")
        if not parsed.netloc:
            raise ValueError("base URL must include a host")
        if parsed.username or parsed.password:
            raise ValueError("base URL must not contain user information")
        if parsed.query or parsed.fragment:
            raise ValueError(
                "base URL must not include a query string or fragment"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        _validate_retry(retry)
        self.base_url = base_url.rstrip("/")
        self._origin = _origin(self.base_url)
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.user_agent = user_agent
        self.retry = retry
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def with_api_key(self, api_key: str) -> Transport:
        """Share connection settings with a separate credential."""
        return Transport(
            base_url=self.base_url,
            api_key=api_key,
            timeout=self.timeout,
            user_agent=self.user_agent,
            retry=self.retry,
            http_client=self.client,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
        options: RequestOptions | None = None,
        skip_auth: bool = False,
    ) -> Any:
        response = self.request_raw(
            method,
            path,
            body=body,
            params=params,
            options=options,
            skip_auth=skip_auth,
        )
        try:
            self._raise_for_status(response, method, path)
            if not response.content and response.status_code in {204, 205}:
                return None
            try:
                envelope = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ProtocolError(
                    f"decode {method.upper()} {path} response: {exc}"
                ) from exc
            if not isinstance(envelope, dict) or "status" not in envelope:
                raise ProtocolError(
                    f"decode {method.upper()} {path} response: "
                    "invalid JSend envelope"
                )
            if envelope["status"] != "success":
                message = envelope.get("message") or "unexpected JSend status"
                raise ProtocolError(str(message))
            return envelope.get("data")
        finally:
            response.close()

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        raw_body: Any = None,
        content_type: str | None = None,
        params: dict[str, Any] | None = None,
        options: RequestOptions | None = None,
        skip_auth: bool = False,
        stream: bool = False,
    ) -> httpx.Response:
        options = options or RequestOptions()
        retry = options.retry or self.retry
        _validate_retry(retry)
        attempts = (
            0
            if options.disable_retry or raw_body is not None or stream
            else retry.max_retries
        )
        url = self._url(path)
        headers = {
            key: value
            for key, value in options.headers.items()
            if key.lower() not in _SENSITIVE
        }
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", self.user_agent)
        if not skip_auth:
            if not self.api_key:
                raise AuthenticationError(
                    "authentication is required: configure an API key"
                )
            headers["X-Api-Key"] = self.api_key
        content = None
        json_body = None
        if body is not None and raw_body is not None:
            raise ValueError("request cannot have both body and raw_body")
        if body is not None:
            json_body = _serialize(body)
        elif raw_body is not None:
            content = raw_body
            if content_type:
                headers["Content-Type"] = content_type
        for attempt in range(attempts + 1):
            try:
                request = self.client.build_request(
                    method.upper(),
                    url,
                    params=params,
                    headers=headers,
                    json=json_body,
                    content=content,
                )
                # A supplied httpx.Client can contribute default credentials
                # after the per-request headers above have been filtered.
                for name in _SENSITIVE:
                    request.headers.pop(name, None)
                if not skip_auth:
                    request.headers["X-Api-Key"] = self.api_key
                request_timeout = (
                    options.timeout
                    if options.timeout is not None
                    else self.timeout
                )
                request.extensions["timeout"] = {
                    "connect": request_timeout,
                    "read": request_timeout,
                    "write": request_timeout,
                    "pool": request_timeout,
                }
                response = self.client.send(
                    request, stream=True, auth=None, follow_redirects=False
                )
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt >= attempts or not _idempotent(method):
                    raise
                time.sleep(_backoff(attempt, retry))
                continue
            if 300 <= response.status_code < 400 and response.headers.get(
                "location"
            ):
                destination = urljoin(
                    str(response.url), response.headers["location"]
                )
                response.close()
                if _origin(destination) != self._origin:
                    raise ProtocolError(
                        "refusing redirect to non-base origin "
                        f"{_origin(destination)!r}"
                    )
                raise ProtocolError("unexpected redirect response")
            if attempt >= attempts or not _retryable(
                method, response.status_code
            ):
                if not stream and 200 <= response.status_code < 300:
                    try:
                        response.read()
                    except Exception:
                        response.close()
                        raise
                return response
            delay = _retry_after(response.headers.get("retry-after"))
            response.close()
            time.sleep(delay if delay is not None else _backoff(attempt, retry))
        raise AssertionError("unreachable")

    def stream(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.request_raw(method, path, stream=True, **kwargs)
        self._raise_for_status(response, method, path)
        return response

    def _url(self, path: str) -> str:
        # Keep endpoints relative to the configured base path, even when the
        # endpoint has a leading slash.
        url = f"{self.base_url}/{path.lstrip('/')}"
        if _origin(url) != self._origin:
            raise ValueError("request URL must use the configured base origin")
        return url

    @staticmethod
    def _raise_for_status(
        response: httpx.Response, method: str, path: str
    ) -> None:
        if 200 <= response.status_code < 300:
            return
        try:
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=64 << 10):
                body.extend(chunk[: (4 << 20) - len(body)])
                if len(body) == 4 << 20:
                    break
            raise APIError(
                status_code=response.status_code,
                method=method,
                endpoint=path,
                body=bytes(body),
                headers=response.headers,
            )
        finally:
            response.close()


_SENSITIVE = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "cookie",
    "set-cookie",
    "x-csrf-token",
}


def _serialize(value: Any) -> Any:
    if isinstance(value, Model):
        return value.to_dict()
    if hasattr(value, "value"):
        return value.value
    return value


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _idempotent(method: str) -> bool:
    return method.upper() in {"GET", "HEAD", "PUT", "DELETE"}


def _retryable(method: str, status: int) -> bool:
    return status in {429, 503} or (
        _idempotent(method) and status in {408, 500, 502, 504}
    )


def _validate_retry(retry: RetryOptions) -> None:
    if (
        retry.max_retries < 0
        or retry.base_delay <= 0
        or retry.max_delay < retry.base_delay
    ):
        raise ValueError("retry configuration is invalid")


def _backoff(attempt: int, retry: RetryOptions) -> float:
    return min(
        retry.base_delay * (2 ** min(attempt, 30))
        + random.random() * retry.base_delay,
        retry.max_delay,
    )


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        try:
            date = email.utils.parsedate_to_datetime(value)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None
