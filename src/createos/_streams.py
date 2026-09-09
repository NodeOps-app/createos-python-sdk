from __future__ import annotations

import base64
import json
from collections import deque
from collections.abc import Iterator
from typing import Any, Generic, TypeVar

import httpx

from .errors import ProtocolError
from .models import (
    CommandStreamEvent,
    ExecStreamEventType,
    ManagedProcessConnectEvent,
    ManagedProcessConnectEventType,
    ManagedProcessStream,
    Model,
    TemplateLogEvent,
)

T = TypeVar("T")


class BinaryStream:
    """A closeable, context-managed streaming HTTP response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def headers(self) -> httpx.Headers:
        return self._response.headers

    def read(self) -> bytes:
        return self._response.read()

    def iter_bytes(self, chunk_size: int | None = None):
        return self._response.iter_bytes(chunk_size)

    def close(self) -> None:
        self._response.close()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class NDJSONStream(Generic[T], Iterator[T]):
    model: type[Model]

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._lines = response.iter_lines()
        self._closed = False

    def __iter__(self):
        return self

    def __next__(self) -> T:
        return self.decode(self._next_payload())

    def _next_payload(self) -> dict[str, Any]:
        while True:
            try:
                line = next(self._lines).strip()
            except StopIteration:
                self.close()
                raise
            # Accept both raw NDJSON and the control lines used by SSE streams.
            if not line or line.startswith((":", "event:", "id:", "retry:")):
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
                if not line:
                    continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                self.close()
                raise ProtocolError(f"decode NDJSON event: {exc}") from exc
            if not isinstance(data, dict):
                self.close()
                raise ProtocolError(
                    "decode NDJSON event: expected a JSON object"
                )
            return data

    def decode(self, data: dict[str, Any]) -> T:
        return self.model.from_dict(data)  # type: ignore[return-value]

    def receive(self) -> T:
        return next(self)

    recv = receive

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._response.close()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class CommandStream(NDJSONStream[CommandStreamEvent]):
    model = CommandStreamEvent

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(response)
        self._queued: deque[CommandStreamEvent] = deque()

    def __next__(self) -> CommandStreamEvent:
        while not self._queued:
            data = self._next_payload()
            # One wire frame may contain output, an error, and an exit status.
            if data.get("hb"):
                self._queued.append(
                    CommandStreamEvent(type=ExecStreamEventType.HEARTBEAT)
                )
            if data.get("stdout"):
                self._queued.append(
                    CommandStreamEvent(
                        type=ExecStreamEventType.STDOUT, data=data["stdout"]
                    )
                )
            if data.get("stderr"):
                self._queued.append(
                    CommandStreamEvent(
                        type=ExecStreamEventType.STDERR, data=data["stderr"]
                    )
                )
            if data.get("error"):
                self._queued.append(
                    CommandStreamEvent(
                        type=ExecStreamEventType.ERROR,
                        error_message=data["error"],
                    )
                )
            if data.get("exit_code") is not None:
                self._queued.append(
                    CommandStreamEvent(
                        type=ExecStreamEventType.EXIT,
                        exit_code=data["exit_code"],
                    )
                )
        return self._queued.popleft()


class ProcessStream(NDJSONStream[ManagedProcessConnectEvent]):
    def decode(self, data: dict[str, Any]) -> ManagedProcessConnectEvent:
        raw = data.get("data_base64", "")
        try:
            decoded = base64.b64decode(raw, validate=True) if raw else b""
        except ValueError as exc:
            raise ProtocolError(f"decode process output: {exc}") from exc
        return ManagedProcessConnectEvent(
            type=ManagedProcessConnectEventType(data["type"]),
            sequence=data.get("seq", 0),
            stream=ManagedProcessStream(data["stream"])
            if data.get("stream")
            else None,
            data=decoded,
            exit_code=data.get("exit_code"),
            signal=data.get("signal"),
            error_message=data.get("error", ""),
            oldest_available_sequence=data.get("oldest_available_seq", 0),
        )


class TemplateLogStream(NDJSONStream[TemplateLogEvent]):
    model = TemplateLogEvent
