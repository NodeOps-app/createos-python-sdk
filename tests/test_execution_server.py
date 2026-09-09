"""Tests for the HTTP execution server example."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from createos import CommandResult, RunCommandResponse

_MODULE_PATH = (
    Path(__file__).parents[1] / "examples" / "execution_server" / "main.py"
)
_SPEC = importlib.util.spec_from_file_location("execution_server", _MODULE_PATH)
assert _SPEC and _SPEC.loader
execution_server = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(execution_server)


class _FakeSandbox:
    def __init__(self) -> None:
        self.destroyed = False
        self.request = None

    def run_command(self, request, options=None):
        self.request = request
        return RunCommandResponse(
            result=CommandResult(standard_output="hello\n", exit_code=0),
            execution_milliseconds=12.5,
        )

    def destroy(self) -> None:
        self.destroyed = True


def test_execution_runs_command_and_destroys_sandbox() -> None:
    sandbox = _FakeSandbox()
    application = execution_server._ExecutionApplication(lambda: sandbox, 1)

    status, response = application.execute(
        json.dumps({"command": "printf", "arguments": ["hello\\n"]}).encode()
    )

    assert status == 200
    assert response["stdout"] == "hello\n"
    assert response["exitCode"] == 0
    assert response["executionMilliseconds"] == 12.5
    assert sandbox.destroyed
    assert sandbox.request.command == "printf"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"{}", "command is required"),
        (b'{"command":"true","unknown":1}', "unknown field"),
        (b'{"command":"true"}{}', "invalid JSON request"),
        (b"[]", "one JSON object"),
    ],
)
def test_execution_rejects_invalid_requests(body: bytes, message: str) -> None:
    application = execution_server._ExecutionApplication(
        lambda: pytest.fail("creator must not be called"),
        1,
    )

    status, response = application.execute(body)

    assert status == 400
    assert message in response["error"]
