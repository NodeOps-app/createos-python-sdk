from __future__ import annotations

import json

import httpx
import pytest

from createos import (
    APIError,
    AuthenticationError,
    Client,
    CommandStreamEvent,
    CreateSandboxRequest,
    ExecStreamEventType,
    ForkSandboxRequest,
    ManagedProcessConnectEvent,
    ProtocolError,
    RequestOptions,
    RunCommandRequest,
    SandboxStatus,
)


def envelope(data, status_code=200, headers=None):
    return httpx.Response(
        status_code,
        json={"status": "success", "data": data},
        headers=headers,
    )


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_health_omits_auth_and_whoami_sends_it():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/healthz":
            return envelope({"up": True})
        return envelope({"user_id": "user-1", "stats": {"total": 1}})

    client = Client(
        api_key="secret",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    assert client.health().up is True
    assert client.who_am_i().user_id == "user-1"
    assert "x-api-key" not in seen[0].headers
    assert seen[1].headers["x-api-key"] == "secret"


def test_client_uses_createos_api_key_environment_variable(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return envelope({"user_id": "user-1", "stats": {"total": 1}})

    monkeypatch.setenv("CREATEOS_API_KEY", "new-key")
    with Client(
        base_url="https://example.test", http_client=mock_client(handler)
    ) as client:
        client.who_am_i()
    assert seen[0].headers["x-api-key"] == "new-key"

    monkeypatch.delenv("CREATEOS_API_KEY")
    with Client(
        base_url="https://example.test", http_client=mock_client(handler)
    ) as client:
        with pytest.raises(AuthenticationError):
            client.who_am_i()
    assert len(seen) == 1


def test_create_initializes_state_services_and_clear_wire_fields():
    requests = []

    def handler(request):
        requests.append(request)
        return envelope(
            {
                "id": "sb-1",
                "status": "paused",
                "name": "demo",
                "ip": "10.0.0.2",
                "shape": "s-4vcpu-4gb",
                "mem_mib": 4096,
                "disk_mib": 8192,
                "ingress_url_template": "https://<port>-sb-1.example.test",
            }
        )

    client = Client(
        api_key="key",
        base_url="https://example.test/api",
        http_client=mock_client(handler),
    )
    sandbox = client.create_sandbox(
        CreateSandboxRequest(
            shape="s-4vcpu-4gb", name="demo", ingress_enabled=True
        )
    )
    assert requests[0].url.path == "/api/v1/sandboxes"
    assert sandbox.id == "sb-1"
    assert sandbox.status is SandboxStatus.PAUSED
    assert sandbox.files and sandbox.processes and sandbox.computer.mouse
    assert sandbox.preview_url(8080) == "https://8080-sb-1.example.test"


def test_projected_stream_response_aliases_match_go_contract():
    command = CommandStreamEvent.from_dict({"type": "exit", "exitCode": 17})
    process = ManagedProcessConnectEvent.from_dict(
        {
            "type": "exit",
            "exitCode": 23,
            "oldestAvailableSeq": 9,
        }
    )

    assert command.exit_code == 17
    assert command.to_dict()["exitCode"] == 17
    assert process.exit_code == 23
    assert process.oldest_available_sequence == 9
    assert process.to_dict()["oldestAvailableSeq"] == 9


def test_destroy_uses_response_status_without_a_fallback():
    def handler(request):
        if request.method == "GET":
            return envelope({"id": "sb-1", "status": "running"})
        return envelope({"id": "sb-1", "status": "destroyed"})

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandbox = client.get_sandbox("sb-1")
    sandbox.destroy()

    assert sandbox.status is SandboxStatus.DESTROYED


def test_destroy_rejects_a_response_without_status():
    def handler(request):
        if request.method == "GET":
            return envelope({"id": "sb-1", "status": "running"})
        return envelope({"id": "sb-1"})

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandbox = client.get_sandbox("sb-1")

    with pytest.raises(ProtocolError, match="DestroyedResponse"):
        sandbox.destroy()
    assert sandbox.status is SandboxStatus.RUNNING


def test_fork_serializes_explicit_false():
    bodies = []

    def handler(request):
        if request.method == "GET":
            return envelope({"id": "source", "status": "running"})
        bodies.append(json.loads(request.content))
        return envelope({"id": "fork-1", "status": "paused"})

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandbox = client.get_sandbox("source")
    clone = sandbox.fork(ForkSandboxRequest(ingress_enabled=False))
    assert clone.id == "fork-1"
    assert bodies[-1] == {"ingress_enabled": False}


def test_api_error_is_inspectable():
    def handler(request):
        return httpx.Response(
            404,
            json={"status": "error", "message": "not found", "code": 42},
            headers={"X-Request-ID": "req-1"},
        )

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    with pytest.raises(APIError) as caught:
        client.get_sandbox("missing")
    assert caught.value.status_code == 404
    assert caught.value.code == 42
    assert caught.value.request_id == "req-1"


def test_list_sandboxes_walks_pages():
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        rows = [
            {"id": f"sb-{index}", "status": "running"}
            for index in range(offset, min(offset + 2, 3))
        ]
        return envelope(
            {
                "data": rows,
                "pagination": {
                    "total": 3,
                    "offset": offset,
                    "count": len(rows),
                },
            }
        )

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandboxes = client.list_sandboxes()
    assert [item.id for item in sandboxes] == ["sb-0", "sb-1", "sb-2"]
    assert offsets == [0, 2]


def test_command_stream_projects_frames_and_accepts_sse():
    payload = (
        b': keepalive\ndata: {"stdout":"hi","stderr":"warn"}\n{"exit_code":0}\n'
    )

    def handler(request):
        if request.method == "GET":
            return envelope({"id": "sb-1", "status": "running"})
        return httpx.Response(200, content=payload)

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandbox = client.get_sandbox("sb-1")
    with sandbox.stream_command(RunCommandRequest(command="echo")) as stream:
        events = list(stream)
    assert [event.type for event in events] == [
        ExecStreamEventType.STDOUT,
        ExecStreamEventType.STDERR,
        ExecStreamEventType.EXIT,
    ]
    assert events[-1].exit_code == 0


def test_file_transfers_use_operation_timeout():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/sandboxes/sb-1":
            return envelope({"id": "sb-1", "status": "running"})
        if request.method == "PUT":
            assert request.content == b"contents"
            return envelope({"bytes": 8, "path": "/workspace/file.txt"})
        return httpx.Response(200, content=b"contents")

    client = Client(
        api_key="key",
        base_url="https://example.test",
        http_client=mock_client(handler),
    )
    sandbox = client.get_sandbox("sb-1")
    sandbox.files.upload(
        "/workspace/file.txt",
        b"contents",
        RequestOptions(timeout=300),
    )
    with sandbox.files.download(
        "/workspace/file.txt",
        RequestOptions(timeout=600),
    ) as download:
        assert download.read() == b"contents"

    upload_timeout = requests[1].extensions["timeout"]
    download_timeout = requests[2].extensions["timeout"]
    assert set(upload_timeout.values()) == {300}
    assert set(download_timeout.values()) == {600}
