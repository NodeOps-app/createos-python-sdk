"""Resource-specific services exposed by the CreateOS API."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ._streams import BinaryStream, ProcessStream, TemplateLogStream
from .errors import ProtocolError
from .models import (
    ComputerButtonRequest,
    ComputerClickRequest,
    ComputerClipboard,
    ComputerCreateScreenRequest,
    ComputerDragRequest,
    ComputerLaunchRequest,
    ComputerListWindowsOptions,
    ComputerOpenRequest,
    ComputerPoint,
    ComputerScreen,
    ComputerScreenConnection,
    ComputerScreenGeometry,
    ComputerScreenID,
    ComputerScreenOptions,
    ComputerScreenshotOptions,
    ComputerScrollRequest,
    ComputerTypeRequest,
    ComputerWindow,
    ComputerWindowGeometry,
    ComputerWindowMoveRequest,
    ComputerWindowResizeRequest,
    Disk,
    DiskCreateRequest,
    DiskCredentials,
    GetTemplateOptions,
    ManagedProcess,
    ManagedProcessConnectOptions,
    ManagedProcessCreateRequest,
    ManagedProcessDeleteOptions,
    ManagedProcessSignal,
    ManagedProcessWaitOptions,
    Network,
    NetworkCreateRequest,
    PaginationOptions,
    PTYSize,
    RequestOptions,
    Template,
    TemplateCreateRequest,
    TemplateLogsOptions,
)

if TYPE_CHECKING:
    from ._transport import Transport
    from .instance import SandboxInstance


def _segment(value: Any) -> str:
    return quote(str(value), safe="")


def _one(model, data):
    try:
        return model.from_dict(data or {})
    except (TypeError, ValueError) as error:
        raise ProtocolError(
            f"decode {model.__name__} response: {error}"
        ) from error


def _many(model, data, legacy_key: str = ""):
    values: Any
    if isinstance(data, list):
        values = data
    elif isinstance(data, dict):
        values = data.get("data")
        if values is None and legacy_key:
            values = data.get(legacy_key)
        values = values or []
    else:
        values = []
    return [model.from_dict(value) for value in values]


def _request_options(options: RequestOptions) -> RequestOptions:
    return RequestOptions(
        headers=options.headers,
        timeout=options.timeout,
        retry=options.retry,
        disable_retry=options.disable_retry,
    )


def _fetch_all(
    transport,
    path,
    model,
    options,
    *,
    params=None,
    legacy_key="",
    skip_auth=False,
):
    params = dict(params or {})
    offset = options.offset
    result = []
    while options.limit <= 0 or len(result) < options.limit:
        page_size = (
            min(500, options.limit - len(result)) if options.limit else 500
        )
        params.update(limit=page_size, offset=offset)
        data = transport.request(
            "GET", path, params=params, skip_auth=skip_auth
        )
        page = _many(model, data, legacy_key)
        result.extend(page)
        total = (
            data.get("pagination", {}).get("total")
            if isinstance(data, dict)
            else None
        )
        if not page or total is None or offset + len(page) >= total:
            break
        offset += len(page)
    return result[: options.limit or None]


class TemplatesService:
    """Manage custom root filesystem templates."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, options: PaginationOptions | None = None) -> list[Template]:
        """Return templates owned by the caller."""
        return _fetch_all(
            self._transport,
            "/v1/templates",
            Template,
            options or PaginationOptions(),
            legacy_key="templates",
        )

    def create(self, request: TemplateCreateRequest) -> Template:
        """Submit a Dockerfile template build."""
        return _one(
            Template,
            self._transport.request("POST", "/v1/templates", body=request),
        )

    def get(
        self, template_id: str, options: GetTemplateOptions | None = None
    ) -> Template:
        """Return a template by ID."""
        options = options or GetTemplateOptions()
        params = {"include": str(options.include)} if options.include else None
        data = self._transport.request(
            "GET",
            f"/v1/templates/{_segment(template_id)}",
            params=params,
            options=_request_options(options),
        )
        return _one(Template, data)

    def delete(self, template_id: str) -> None:
        """Delete a template without affecting existing sandboxes."""
        self._transport.request(
            "DELETE", f"/v1/templates/{_segment(template_id)}"
        )

    def logs(
        self, template_id: str, options: TemplateLogsOptions | None = None
    ) -> str:
        """Return the template build log collected so far."""
        options = options or TemplateLogsOptions()
        path = f"/v1/templates/{_segment(template_id)}/logs"
        params = {"attempt": options.attempt} if options.attempt else None
        response = self._transport.request_raw(
            "GET", path, params=params, options=_request_options(options)
        )
        try:
            self._transport._raise_for_status(response, "GET", path)
            return response.text
        finally:
            response.close()

    def follow_logs(
        self, template_id: str, options: TemplateLogsOptions | None = None
    ) -> TemplateLogStream:
        """Follow template build events as a context-managed stream."""
        options = options or TemplateLogsOptions()
        params = {"follow": "true"}
        if options.attempt:
            params["attempt"] = str(options.attempt)
        response = self._transport.stream(
            "GET",
            f"/v1/templates/{_segment(template_id)}/logs",
            params=params,
            options=_request_options(options),
        )
        return TemplateLogStream(response)


class NetworksService:
    """Manage account-level overlay networks."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, options: PaginationOptions | None = None) -> list[Network]:
        """Return overlay networks owned by the caller."""
        return _fetch_all(
            self._transport,
            "/v1/networks",
            Network,
            options or PaginationOptions(),
        )

    def create(self, request: NetworkCreateRequest) -> Network:
        """Create an overlay network."""
        return _one(
            Network,
            self._transport.request("POST", "/v1/networks", body=request),
        )

    def get(self, network_id: str) -> Network:
        """Return an overlay network by ID."""
        return _one(
            Network,
            self._transport.request(
                "GET", f"/v1/networks/{_segment(network_id)}"
            ),
        )

    def delete(self, network_id: str) -> None:
        """Delete an overlay network."""
        self._transport.request(
            "DELETE", f"/v1/networks/{_segment(network_id)}"
        )


class DisksService:
    """Manage account-level persistent disk registrations."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, options: PaginationOptions | None = None) -> list[Disk]:
        """Return disks registered by the caller."""
        return _fetch_all(
            self._transport,
            "/v1/disks",
            Disk,
            options or PaginationOptions(),
            legacy_key="disks",
        )

    def create(self, request: DiskCreateRequest) -> Disk:
        """Register an S3-compatible persistent disk."""
        return _one(
            Disk, self._transport.request("POST", "/v1/disks", body=request)
        )

    def get(self, disk_id_or_name: str) -> Disk:
        """Return a disk by ID or user-scoped name."""
        return _one(
            Disk,
            self._transport.request(
                "GET", f"/v1/disks/{_segment(disk_id_or_name)}"
            ),
        )

    def delete(self, disk_id_or_name: str) -> bool:
        """Delete a disk registration without modifying bucket contents."""
        data = self._transport.request(
            "DELETE", f"/v1/disks/{_segment(disk_id_or_name)}"
        )
        return bool((data or {}).get("deleted"))

    def rotate_credentials(
        self, disk_id_or_name: str, credentials: DiskCredentials
    ) -> Disk:
        """Replace a disk's stored credentials."""
        body = {"credentials": credentials.to_dict()}
        data = self._transport.request(
            "PATCH", f"/v1/disks/{_segment(disk_id_or_name)}", body=body
        )
        return _one(Disk, data)


class FilesService:
    """Transfer files to and from one sandbox."""

    def __init__(self, instance: SandboxInstance) -> None:
        self._instance = instance

    def upload(
        self,
        path: str,
        data: bytes | bytearray | Any,
        options: RequestOptions | None = None,
    ) -> None:
        """Write binary data with optional per-operation network timeouts."""
        body = bytes(data) if isinstance(data, (bytes, bytearray)) else data
        response = self._instance._transport.request_raw(
            "PUT",
            self._instance._path("/files"),
            params={"path": path},
            raw_body=body,
            content_type="application/octet-stream",
            options=_request_options(options or RequestOptions()),
        )
        try:
            self._instance._transport._raise_for_status(
                response, "PUT", self._instance._path("/files")
            )
        finally:
            response.close()

    def download(
        self,
        path: str,
        options: RequestOptions | None = None,
    ) -> BinaryStream:
        """Open a file stream with optional per-operation network timeouts."""
        endpoint = self._instance._path("/files")
        response = self._instance._transport.stream(
            "GET",
            endpoint,
            params={"path": path},
            options=_request_options(options or RequestOptions()),
        )
        return BinaryStream(response)


class ProcessesService:
    """Manage persistent processes and PTYs in one sandbox."""

    def __init__(self, instance: SandboxInstance) -> None:
        self._instance = instance

    def _path(self, process_id: str = "", suffix: str = "") -> str:
        path = self._instance._path("/processes")
        return (
            path + (f"/{_segment(process_id)}" if process_id else "") + suffix
        )

    def create(self, request: ManagedProcessCreateRequest) -> ManagedProcess:
        """Start a managed process or PTY."""
        return _one(
            ManagedProcess,
            self._instance._transport.request(
                "POST", self._path(), body=request
            ),
        )

    def list(self) -> list[ManagedProcess]:
        """Return retained managed processes and PTYs."""
        data = self._instance._transport.request("GET", self._path()) or {}
        return _many(ManagedProcess, data.get("processes", []))

    def get(self, process_id: str) -> ManagedProcess:
        """Return one managed process."""
        return _one(
            ManagedProcess,
            self._instance._transport.request("GET", self._path(process_id)),
        )

    def connect(
        self,
        process_id: str,
        options: ManagedProcessConnectOptions | None = None,
    ) -> ProcessStream:
        """Open a replayable process output stream."""
        options = options or ManagedProcessConnectOptions()
        response = self._instance._transport.stream(
            "GET",
            self._path(process_id, "/connect"),
            params={"after": options.after_sequence},
            options=_request_options(options),
        )
        return ProcessStream(response)

    def input(self, process_id: str, data: str) -> int:
        """Write UTF-8 input and return its sequence number."""
        return self.input_bytes(process_id, data.encode())

    def input_bytes(self, process_id: str, data: bytes) -> int:
        """Write binary input and return its sequence number."""
        body = {"data_base64": base64.b64encode(data).decode()}
        result = self._instance._transport.request(
            "POST", self._path(process_id, "/input"), body=body
        )
        return int(result["input_seq"])

    def close_standard_input(self, process_id: str) -> None:
        """Close a pipe process's standard input."""
        self._instance._transport.request(
            "POST", self._path(process_id, "/stdin/close")
        )

    def resize(self, process_id: str, size: PTYSize) -> None:
        """Change PTY dimensions."""
        self._instance._transport.request(
            "POST", self._path(process_id, "/resize"), body=size
        )

    def signal(self, process_id: str, signal: ManagedProcessSignal) -> None:
        """Send a signal to a managed process."""
        self._instance._transport.request(
            "POST",
            self._path(process_id, "/signal"),
            body={"signal": str(signal)},
        )

    def wait(
        self, process_id: str, options: ManagedProcessWaitOptions | None = None
    ) -> ManagedProcess:
        """Long-poll until a process leader or tree exits."""
        options = options or ManagedProcessWaitOptions()
        params: dict[str, Any] = {}
        if options.scope:
            params["scope"] = str(options.scope)
        if options.wait_timeout:
            params["timeout_ms"] = int(options.wait_timeout * 1000)
        data = self._instance._transport.request(
            "GET",
            self._path(process_id, "/wait"),
            params=params,
            options=_request_options(options),
        )
        return _one(ManagedProcess, data)

    def delete(
        self,
        process_id: str,
        options: ManagedProcessDeleteOptions | None = None,
    ) -> ManagedProcess:
        """Terminate a managed process tree."""
        options = options or ManagedProcessDeleteOptions()
        params = (
            {"grace_ms": int(options.grace_period * 1000)}
            if options.grace_period
            else None
        )
        data = self._instance._transport.request(
            "DELETE",
            self._path(process_id),
            params=params,
            options=_request_options(options),
        )
        return _one(ManagedProcess, data)


class ComputerService:
    """Provide desktop computer-use operations."""

    def __init__(self, instance: SandboxInstance) -> None:
        self._instance = instance
        self.mouse = MouseService(self)
        self.keyboard = KeyboardService(self)
        self.windows = WindowsService(self)
        self.screens = ScreensService(self)

    def _path(self, suffix: str) -> str:
        return self._instance._path("/computer" + suffix)

    def _do(
        self,
        method: str,
        suffix: str,
        options: ComputerScreenOptions | None = None,
        body: Any = None,
    ) -> Any:
        options = options or ComputerScreenOptions()
        params = (
            {"screen_id": str(options.screen_id)} if options.screen_id else {}
        )
        return self._instance._transport.request(
            method,
            self._path(suffix),
            params=params,
            body=body,
            options=_request_options(options),
        )

    def screenshot(
        self, options: ComputerScreenshotOptions | None = None
    ) -> BinaryStream:
        """Capture PNG bytes as a context-managed binary stream."""
        options = options or ComputerScreenshotOptions()
        params = (
            {"screen_id": str(options.screen_id)} if options.screen_id else {}
        )
        for key in ("window_id", "x", "y", "width", "height"):
            value = getattr(options, key)
            if (
                value is not None
                and value != ""
                and (
                    not isinstance(value, int)
                    or value != 0
                    or key in {"x", "y"}
                )
            ):
                params[key] = value
        response = self._instance._transport.stream(
            "GET",
            self._path("/screenshot"),
            params=params,
            options=_request_options(options),
        )
        return BinaryStream(response)

    def screen(
        self, options: ComputerScreenOptions | None = None
    ) -> ComputerScreenGeometry:
        """Return active screen dimensions."""
        return _one(ComputerScreenGeometry, self._do("GET", "/screen", options))

    def cursor(
        self, options: ComputerScreenOptions | None = None
    ) -> ComputerPoint:
        """Return current cursor coordinates."""
        return _one(ComputerPoint, self._do("GET", "/cursor", options))

    def clipboard(
        self, options: ComputerScreenOptions | None = None
    ) -> ComputerClipboard:
        """Return current clipboard text."""
        return _one(ComputerClipboard, self._do("GET", "/clipboard", options))

    def set_clipboard(
        self, text: str, options: ComputerScreenOptions | None = None
    ) -> None:
        """Replace clipboard text."""
        self._do("PUT", "/clipboard", options, {"text": text})

    def open(
        self,
        request: ComputerOpenRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Open a URL or desktop target."""
        self._do("POST", "/open", options, request)

    def launch(
        self,
        request: ComputerLaunchRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Launch an installed desktop application."""
        self._do("POST", "/launch", options, request)


class MouseService:
    """Provide desktop mouse operations."""

    def __init__(self, computer: ComputerService) -> None:
        self._computer = computer

    def move(
        self,
        point: ComputerPoint,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Move the cursor."""
        self._computer._do("POST", "/mouse/move", options, point)

    def click(
        self,
        request: ComputerClickRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Click a mouse button."""
        self._computer._do("POST", "/mouse/click", options, request)

    def scroll(
        self,
        request: ComputerScrollRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Scroll the desktop."""
        self._computer._do("POST", "/mouse/scroll", options, request)

    def drag(
        self,
        request: ComputerDragRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Drag between two points."""
        self._computer._do("POST", "/mouse/drag", options, request)

    def down(
        self,
        request: ComputerButtonRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Press a mouse button."""
        self._computer._do("POST", "/mouse/down", options, request)

    def up(
        self,
        request: ComputerButtonRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Release a mouse button."""
        self._computer._do("POST", "/mouse/up", options, request)


class KeyboardService:
    """Provide desktop keyboard operations."""

    def __init__(self, computer: ComputerService) -> None:
        self._computer = computer

    def type(
        self,
        request: ComputerTypeRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Type text into the active application."""
        self._computer._do("POST", "/keyboard/type", options, request)

    def press(
        self,
        keys: list[str],
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Press and release a key combination."""
        self._computer._do("POST", "/keyboard/press", options, {"keys": keys})

    def down(
        self,
        keys: list[str],
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Press keys without releasing them."""
        self._computer._do("POST", "/keyboard/down", options, {"keys": keys})

    def up(
        self,
        keys: list[str],
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Release keys."""
        self._computer._do("POST", "/keyboard/up", options, {"keys": keys})


class WindowsService:
    """Provide desktop window operations."""

    def __init__(self, computer: ComputerService) -> None:
        self._computer = computer

    def list(
        self, options: ComputerListWindowsOptions | None = None
    ) -> list[ComputerWindow]:
        """Return visible desktop windows."""
        options = options or ComputerListWindowsOptions()
        params = (
            {"screen_id": str(options.screen_id)} if options.screen_id else {}
        )
        if options.application:
            params["application"] = options.application
        data = self._computer._instance._transport.request(
            "GET",
            self._computer._path("/windows"),
            params=params,
            options=_request_options(options),
        )
        return _many(ComputerWindow, data)

    def current(
        self, options: ComputerScreenOptions | None = None
    ) -> ComputerWindow:
        """Return the active window."""
        return _one(
            ComputerWindow,
            self._computer._do("GET", "/windows/current", options),
        )

    def get(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> ComputerWindow:
        """Return a window by ID."""
        return _one(
            ComputerWindow,
            self._computer._do(
                "GET", f"/windows/{_segment(window_id)}", options
            ),
        )

    def geometry(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> ComputerWindowGeometry:
        """Return a window's position and dimensions."""
        return _one(
            ComputerWindowGeometry,
            self._computer._do(
                "GET", f"/windows/{_segment(window_id)}/geometry", options
            ),
        )

    def _action(
        self,
        window_id: str,
        action: str,
        options: ComputerScreenOptions | None = None,
        body: Any = None,
    ) -> None:
        self._computer._do(
            "POST", f"/windows/{_segment(window_id)}/{action}", options, body
        )

    def focus(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Focus a window."""
        self._action(window_id, "focus", options)

    def move(
        self,
        window_id: str,
        request: ComputerWindowMoveRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Move a window."""
        self._action(window_id, "move", options, request)

    def resize(
        self,
        window_id: str,
        request: ComputerWindowResizeRequest,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Resize a window."""
        self._action(window_id, "resize", options, request)

    def maximize(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Maximize a window."""
        self._action(window_id, "maximize", options)

    def minimize(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Minimize a window."""
        self._action(window_id, "minimize", options)

    def restore(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Restore a window."""
        self._action(window_id, "restore", options)

    def close(
        self,
        window_id: str,
        options: ComputerScreenOptions | None = None,
    ) -> None:
        """Close a window."""
        options = options or ComputerScreenOptions()
        self._computer._instance._transport.request(
            "DELETE",
            self._computer._path(f"/windows/{_segment(window_id)}"),
            params={"screen_id": str(options.screen_id)}
            if options.screen_id
            else {},
            options=_request_options(options),
        )


class ScreensService:
    """Provide desktop screen and connection operations."""

    def __init__(self, computer: ComputerService) -> None:
        self._computer = computer

    def _path(self, screen_id: ComputerScreenID, suffix: str = "") -> str:
        return self._computer._path(f"/screens/{_segment(screen_id)}{suffix}")

    def list(self) -> list[ComputerScreen]:
        """Return configured desktop screens."""
        return _many(
            ComputerScreen,
            self._computer._instance._transport.request(
                "GET", self._computer._path("/screens")
            ),
        )

    def create(self, request: ComputerCreateScreenRequest) -> ComputerScreen:
        """Create a desktop screen."""
        return _one(
            ComputerScreen,
            self._computer._instance._transport.request(
                "POST", self._computer._path("/screens"), body=request
            ),
        )

    def get(self, screen_id: ComputerScreenID) -> ComputerScreen:
        """Return a desktop screen by ID."""
        return _one(
            ComputerScreen,
            self._computer._instance._transport.request(
                "GET", self._path(screen_id)
            ),
        )

    def connect(self, screen_id: ComputerScreenID) -> ComputerScreenConnection:
        """Return a temporary noVNC connection."""
        return _one(
            ComputerScreenConnection,
            self._computer._instance._transport.request(
                "GET", self._path(screen_id, "/connect")
            ),
        )

    def resize(
        self,
        screen_id: ComputerScreenID,
        request: ComputerCreateScreenRequest,
    ) -> ComputerScreen:
        """Resize a desktop screen."""
        return _one(
            ComputerScreen,
            self._computer._instance._transport.request(
                "POST", self._path(screen_id, "/resize"), body=request
            ),
        )

    def delete(self, screen_id: ComputerScreenID) -> None:
        """Delete a desktop screen."""
        self._computer._instance._transport.request(
            "DELETE", self._path(screen_id)
        )
