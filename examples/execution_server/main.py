"""Expose CreateOS sandbox command execution through a local HTTP API."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from createos import (
    Client,
    CreateSandboxRequest,
    ExecOptions,
    RequestOptions,
    RunCommandRequest,
    SandboxInstance,
)

_DEFAULT_ADDRESS = "127.0.0.1:8080"
_MAXIMUM_REQUEST_BYTES = 1 << 20
_MAXIMUM_CONCURRENCY = 4
_EXECUTION_TIMEOUT = 120.0


class _Sandbox(Protocol):
    def run_command(
        self,
        request: RunCommandRequest,
        options: ExecOptions | None = None,
    ) -> Any:
        """Run a command in the sandbox."""

    def destroy(self) -> None:
        """Destroy the sandbox."""


class _ExecutionApplication:
    """Validate execution requests and run them in fresh sandboxes."""

    def __init__(
        self,
        create_sandbox: Callable[[], _Sandbox],
        concurrency: int,
    ) -> None:
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        self._create_sandbox = create_sandbox
        self._slots = threading.BoundedSemaphore(concurrency)

    def execute(self, body: bytes) -> tuple[HTTPStatus, dict[str, Any]]:
        """Validate and execute one JSON request body."""
        if len(body) > _MAXIMUM_REQUEST_BYTES:
            return self._error(
                HTTPStatus.BAD_REQUEST, "request body is too large"
            )
        if not self._slots.acquire(blocking=False):
            return self._error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "execution capacity reached",
            )
        try:
            request, error = _decode_request(body)
            if error:
                return self._error(HTTPStatus.BAD_REQUEST, error)
            return self._run(request)
        finally:
            self._slots.release()

    def _run(
        self, request: dict[str, Any]
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        started = time.monotonic()
        try:
            sandbox = self._create_sandbox()
        except Exception as error:  # The example converts SDK failures to HTTP.
            return self._execution_error("create sandbox", error, started)

        try:
            elapsed = time.monotonic() - started
            remaining = max(0.001, _EXECUTION_TIMEOUT - elapsed)
            result = sandbox.run_command(
                RunCommandRequest(
                    command=request["command"],
                    arguments=request.get("arguments", []),
                    standard_input=request.get("standardInput", ""),
                    environment_variables=request.get(
                        "environmentVariables", {}
                    ),
                ),
                ExecOptions(timeout=remaining),
            )
            response = {
                "stdout": result.result.standard_output,
                "stderr": result.result.standard_error,
                "exitCode": result.result.exit_code,
                "executionMilliseconds": result.execution_milliseconds,
            }
            if result.result.error_message:
                response["error"] = result.result.error_message
            return HTTPStatus.OK, response
        except Exception as error:  # The example converts SDK failures to HTTP.
            return self._execution_error("execute command", error, started)
        finally:
            try:
                sandbox.destroy()
            except Exception:  # Cleanup errors cannot change a written result.
                logging.exception("destroy sandbox")

    @staticmethod
    def _execution_error(
        operation: str,
        error: Exception,
        started: float,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        timed_out = (
            isinstance(error, TimeoutError)
            or time.monotonic() - started >= _EXECUTION_TIMEOUT
        )
        status = (
            HTTPStatus.GATEWAY_TIMEOUT if timed_out else HTTPStatus.BAD_GATEWAY
        )
        return status, {"error": f"{operation} failed: {error}"}

    @staticmethod
    def _error(
        status: HTTPStatus, message: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        return status, {"error": message}


def _decode_request(
    body: bytes,
) -> tuple[dict[str, Any], str | None]:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return {}, f"invalid JSON request: {error}"
    if not isinstance(value, dict):
        return {}, "request body must contain one JSON object"

    allowed = {
        "command",
        "arguments",
        "standardInput",
        "environmentVariables",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        return {}, f"unknown field: {unknown[0]}"
    if not isinstance(value.get("command"), str):
        return {}, "command is required"
    value["command"] = value["command"].strip()
    if not value["command"]:
        return {}, "command is required"
    if not _is_string_list(value.get("arguments", [])):
        return {}, "arguments must be an array of strings"
    if not isinstance(value.get("standardInput", ""), str):
        return {}, "standardInput must be a string"
    environment = value.get("environmentVariables", {})
    if not isinstance(environment, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in environment.items()
    ):
        return {}, "environmentVariables must contain string values"
    return value, None


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) for item in value
    )


def _handler(
    application: _ExecutionApplication,
) -> type[BaseHTTPRequestHandler]:
    class ExecutionHandler(BaseHTTPRequestHandler):
        """Handle requests for one execution application."""

        def do_POST(self) -> None:  # pylint: disable=invalid-name
            """Execute a command for POST requests to the execution route."""
            if self.path != "/v1/execute":
                self._write(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._write(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid Content-Length"},
                )
                return
            if length < 0:
                self._write(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid Content-Length"},
                )
                return
            body = self.rfile.read(min(length, _MAXIMUM_REQUEST_BYTES + 1))
            self._write(*application.execute(body))

        def do_GET(self) -> None:  # pylint: disable=invalid-name
            """Reject GET requests with the appropriate route status."""
            if self.path == "/v1/execute":
                self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
                self.send_header("Allow", "POST")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"method not allowed"}\n')
                return
            self._write(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def _write(self, status: HTTPStatus, value: dict[str, Any]) -> None:
            payload = json.dumps(value, separators=(",", ":")).encode() + b"\n"
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ExecutionHandler


def main() -> None:
    """Run the local execution server until interrupted."""
    api_key = os.getenv("CREATEOS_SANDBOX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("CREATEOS_SANDBOX_API_KEY is required")
    address = os.getenv("EXECUTION_SERVER_ADDRESS", _DEFAULT_ADDRESS).strip()
    host, separator, port_text = address.rpartition(":")
    if not separator or not host:
        raise SystemExit(
            "EXECUTION_SERVER_ADDRESS must have the form host:port"
        )

    client = Client(api_key=api_key)

    def create_sandbox() -> SandboxInstance:
        return client.create_sandbox(
            CreateSandboxRequest(shape="s-1vcpu-1gb", rootfs="devbox:1"),
            RequestOptions(timeout=_EXECUTION_TIMEOUT),
        )

    application = _ExecutionApplication(
        create_sandbox,
        concurrency=_MAXIMUM_CONCURRENCY,
    )
    server = ThreadingHTTPServer(
        (host, int(port_text)),
        _handler(application),
    )
    logging.warning("execution server listening on %s", address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        client.close()


if __name__ == "__main__":
    main()
