"""Stateful handles for individual CreateOS sandboxes."""

from __future__ import annotations

import copy
import re
import threading
import time
from urllib.parse import quote

from ._streams import CommandStream
from .errors import CommandError, OperationTimeout
from .models import (
    AttachDiskOptions,
    BandwidthView,
    DestroyedResponse,
    DetachDiskOptions,
    DiskAttachment,
    EgressView,
    ExecOptions,
    ForkSandboxRequest,
    PaginationOptions,
    ResizeSandboxResponse,
    RunCommandRequest,
    RunCommandResponse,
    Sandbox,
    SandboxDisk,
    SandboxStatus,
    WaitOptions,
)
from .services import (
    ComputerService,
    FilesService,
    ProcessesService,
    _fetch_all,
    _one,
    _request_options,
)


class SandboxInstance:
    """A stateful handle to one sandbox and its nested services."""

    def __init__(self, transport, data: Sandbox) -> None:
        self._transport = transport
        self._data = data
        self._lock = threading.RLock()
        self.files = FilesService(self)
        self.processes = ProcessesService(self)
        self.computer = ComputerService(self)

    @property
    def id(self) -> str:
        """Return the sandbox identifier."""
        return self._snapshot().id

    @property
    def name(self) -> str:
        """Return the user-visible sandbox name."""
        return self._snapshot().name or ""

    @property
    def status(self) -> SandboxStatus:
        """Return the last observed lifecycle status."""
        return self._snapshot().status

    @property
    def ip_address(self) -> str:
        """Return the last observed private IP address."""
        return self._snapshot().ip_address or ""

    @property
    def data(self) -> Sandbox:
        """Return a copy of the last observed server projection."""
        return self._snapshot()

    def _snapshot(self):
        with self._lock:
            return copy.deepcopy(self._data)

    def _update(self, data):
        with self._lock:
            self._data = data

    def _path(self, suffix: str) -> str:
        return f"/v1/sandboxes/{quote(self.id, safe='')}{suffix}"

    def refresh(self) -> SandboxInstance:
        """Reload the server projection and return this handle."""
        self._update(
            _one(Sandbox, self._transport.request("GET", self._path("")))
        )
        return self

    def _lifecycle(self, suffix: str) -> SandboxInstance:
        self._update(
            _one(Sandbox, self._transport.request("POST", self._path(suffix)))
        )
        return self

    def pause(self) -> SandboxInstance:
        """Snapshot and pause the sandbox."""
        return self._lifecycle("/pause")

    def resume(self) -> SandboxInstance:
        """Restore the paused sandbox."""
        return self._lifecycle("/resume")

    def fork(
        self, request: ForkSandboxRequest | None = None
    ) -> SandboxInstance:
        """Create an independent sandbox from this sandbox."""
        data = self._transport.request(
            "POST", self._path("/fork"), body=request or ForkSandboxRequest()
        )
        return SandboxInstance(self._transport, _one(Sandbox, data))

    def destroy(self) -> None:
        """Start destruction of the sandbox."""
        response = _one(
            DestroyedResponse,
            self._transport.request("DELETE", self._path("")),
        )
        with self._lock:
            self._data.status = response.status

    def resize(self, disk_mib: int) -> ResizeSandboxResponse:
        """Grow the sandbox overlay disk to the requested size."""
        data = self._transport.request(
            "POST", self._path("/resize"), body={"disk_mib": disk_mib}
        )
        result = _one(ResizeSandboxResponse, data)
        with self._lock:
            self._data.disk_mib = result.disk_mib
        return result

    def set_ingress(self, enabled: bool) -> SandboxInstance:
        """Enable or disable public ingress."""
        data = self._transport.request(
            "PATCH", self._path(""), body={"ingress_enabled": enabled}
        )
        self._update(_one(Sandbox, data))
        return self

    def set_auto_pause(self, timeout: float | None) -> SandboxInstance:
        """Set the idle timeout in seconds, or disable it with ``None``."""
        body: dict[str, bool | int]
        if timeout is None:
            body = {"disable_auto_pause": True}
        else:
            if (
                timeout < 60
                or timeout > 86400
                or not float(timeout).is_integer()
            ):
                raise ValueError(
                    "auto-pause timeout must be whole seconds between "
                    "1 minute and 24 hours"
                )
            body = {"auto_pause_after_seconds": int(timeout)}
        self._update(
            _one(
                Sandbox,
                self._transport.request("PATCH", self._path(""), body=body),
            )
        )
        return self

    def add_ssh_public_keys(self, keys: list[str]) -> int:
        """Add OpenSSH public keys and return the resulting key count."""
        data = self._transport.request(
            "POST", self._path("/ssh-pubkeys"), body={"keys": keys}
        )
        return int(data["count"])

    def run_command(
        self, request: RunCommandRequest, options: ExecOptions | None = None
    ) -> RunCommandResponse:
        """Run a command and return its buffered output."""
        request = copy.deepcopy(request)
        options = options or ExecOptions()
        if options.standard_input is not None:
            request.standard_input = options.standard_input
        if options.environment_variables is not None:
            request.environment_variables = options.environment_variables
        request.stream = False
        data = self._transport.request(
            "POST",
            self._path("/exec"),
            body=request,
            options=_request_options(options),
        )
        return _one(RunCommandResponse, data)

    def shell(
        self, script: str, options: ExecOptions | None = None
    ) -> RunCommandResponse:
        """Run a Bash script and raise when it exits unsuccessfully."""
        response = self.run_command(
            RunCommandRequest(command="bash", arguments=["-lc", script]),
            options,
        )
        result = response.result
        if result.exit_code or result.error_message:
            message = f"command exited with status {result.exit_code}"
            if result.error_message:
                message += f"\nerror: {result.error_message}"
            if result.standard_error:
                message += f"\nstderr: {result.standard_error[-2000:]}"
            raise CommandError(message, response)
        return response

    def stream_command(
        self, request: RunCommandRequest, options: ExecOptions | None = None
    ) -> CommandStream:
        """Run a command and return a context-managed event stream."""
        request = copy.deepcopy(request)
        options = options or ExecOptions()
        request.stream = True
        if options.standard_input is not None:
            request.standard_input = options.standard_input
        if options.environment_variables is not None:
            request.environment_variables = options.environment_variables
        response = self._transport.stream(
            "POST",
            self._path("/exec?stream=true"),
            body=request,
            options=_request_options(options),
        )
        return CommandStream(response)

    def wait_until_running(
        self, options: WaitOptions | None = None
    ) -> SandboxInstance:
        """Wait until the sandbox is running."""
        return self._wait_for(
            SandboxStatus.RUNNING,
            {
                SandboxStatus.ERROR,
                SandboxStatus.FAILED,
                SandboxStatus.DESTROYING,
                SandboxStatus.DESTROYED,
            },
            options,
        )

    def wait_until_paused(
        self, options: WaitOptions | None = None
    ) -> SandboxInstance:
        """Wait until the sandbox is paused."""
        return self._wait_for(
            SandboxStatus.PAUSED,
            {
                SandboxStatus.ERROR,
                SandboxStatus.FAILED,
                SandboxStatus.DESTROYING,
                SandboxStatus.DESTROYED,
            },
            options,
        )

    def wait_until_destroyed(
        self, options: WaitOptions | None = None
    ) -> SandboxInstance:
        """Wait until the sandbox is fully destroyed."""
        return self._wait_for(
            SandboxStatus.DESTROYED,
            {SandboxStatus.ERROR, SandboxStatus.FAILED},
            options,
        )

    def _wait_for(self, desired, terminal, options):
        options = options or WaitOptions()
        deadline = time.monotonic() + options.timeout
        while True:
            # Refresh the complete projection so cached properties remain
            # consistent with the status observed by this poll.
            data = _one(
                Sandbox,
                self._transport.request(
                    "GET", self._path(""), options=options.request
                ),
            )
            self._update(data)
            if data.status in terminal:
                raise RuntimeError(
                    f"sandbox {data.id!r} entered terminal state "
                    f"{data.status!r}"
                )
            if data.status == desired:
                return self
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OperationTimeout(
                    f"wait for sandbox {self.id!r} to become {desired!s}"
                )
            time.sleep(min(0.5, remaining))

    def preview_url(self, port: int) -> str:
        """Return the public ingress URL for a sandbox port."""
        if not 1 <= port <= 65535:
            raise ValueError(f"port must be between 1 and 65535, got {port}")
        data = self._snapshot()
        if not data.ingress_enabled or not data.ingress_url_template:
            raise ValueError("sandbox ingress is not enabled")
        return data.ingress_url_template.replace("<port>", str(port))

    def wait_for_port(
        self, port: int, host: str = "127.0.0.1", timeout: float = 30.0
    ) -> None:
        """Wait until a TCP port is listening inside the sandbox."""
        if not 1 <= port <= 65535:
            raise ValueError(f"port must be between 1 and 65535, got {port}")
        if (
            not host
            or not re.fullmatch(r"[A-Za-z0-9.-]+", host)
            or ".." in host
        ):
            raise ValueError(
                f"host {host!r} is not a valid IP address or DNS name"
            )
        seconds = max(1, int(timeout + 0.999))
        script = (
            f"timeout {seconds} bash -c 'until (echo > /dev/tcp/{host}/{port}) "
            "2>/dev/null; do sleep 0.25; done'"
        )
        response = self.run_command(
            RunCommandRequest(command="bash", arguments=["-c", script]),
            ExecOptions(timeout=timeout + 5),
        )
        if response.result.exit_code:
            raise OperationTimeout(
                f"port {port} did not become ready within {timeout}s"
            )

    def egress(self) -> EgressView:
        """Return the current outbound network allowlist."""
        return _one(
            EgressView, self._transport.request("GET", self._path("/egress"))
        )

    def set_egress(self, rules: list[str]) -> EgressView:
        """Replace and return the outbound network allowlist."""
        return _one(
            EgressView,
            self._transport.request(
                "PUT", self._path("/egress"), body={"egress": rules}
            ),
        )

    def bandwidth(self) -> BandwidthView:
        """Return sandbox bandwidth quota and usage counters."""
        return _one(
            BandwidthView,
            self._transport.request("GET", self._path("/bandwidth")),
        )

    def recharge_bandwidth(self, bytes_: int) -> BandwidthView:
        """Add bytes to the sandbox bandwidth quota."""
        return _one(
            BandwidthView,
            self._transport.request(
                "POST",
                self._path("/bandwidth/recharge"),
                body={"add_bytes": bytes_},
            ),
        )

    def attach_network(self, network_id: str) -> None:
        """Connect this sandbox to an overlay network."""
        self._transport.request(
            "POST", self._path("/networks"), body={"id": network_id}
        )

    def detach_network(self, network_id: str) -> None:
        """Disconnect this sandbox from an overlay network."""
        self._transport.request(
            "DELETE", self._path(f"/networks/{quote(network_id, safe='')}")
        )

    def list_disks(
        self, options: PaginationOptions | None = None
    ) -> list[SandboxDisk]:
        """Return persistent disks attached to this sandbox."""
        return _fetch_all(
            self._transport,
            self._path("/disks"),
            SandboxDisk,
            options or PaginationOptions(),
            legacy_key="disks",
        )

    def attach_disk(self, options: AttachDiskOptions) -> None:
        """Mount a registered persistent disk in this sandbox."""
        body = DiskAttachment(
            options.disk_id, options.mount_path, options.sub_path
        )
        data = self._transport.request("POST", self._path("/disks"), body=body)
        if data.get("id") != self.id:
            raise RuntimeError(
                f"server acknowledged sandbox {data.get('id')!r}, "
                f"expected {self.id!r}"
            )

    def detach_disk(self, options: DetachDiskOptions) -> bool:
        """Unmount a persistent disk and report whether it detached."""
        data = self._transport.request(
            "DELETE",
            self._path(f"/disks/{quote(options.disk_id, safe='')}"),
            params={"mount_path": options.mount_path},
        )
        return bool(data.get("detached"))


Instance = SandboxInstance
