"""Typed request, response, option, and enumeration contracts."""

from __future__ import annotations

import types
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class HostStatus(StrEnum):
    ACTIVE = "active"
    DRAINING = "draining"
    DEAD = "dead"


class SandboxStatus(StrEnum):
    CREATING = "creating"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    FORKING = "forking"
    ERROR = "error"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    FAILED = "failed"


class ExecStreamEventType(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT = "exit"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ManagedProcessKind(StrEnum):
    PROCESS = "process"
    PTY = "pty"


class ManagedProcessState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    TERMINATING = "terminating"
    EXITED = "exited"
    FAILED = "failed"


class ManagedProcessSignal(StrEnum):
    HANGUP = "SIGHUP"
    INTERRUPT = "SIGINT"
    QUIT = "SIGQUIT"
    KILL = "SIGKILL"
    TERMINATE = "SIGTERM"
    USER_DEFINED_1 = "SIGUSR1"
    USER_DEFINED_2 = "SIGUSR2"
    WINDOW_CHANGE = "SIGWINCH"


class ManagedProcessStream(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"
    PTY = "pty"


class ManagedProcessConnectEventType(StrEnum):
    DATA = "data"
    EXIT = "exit"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class ComputerScreenID(StrEnum):
    SCREEN_0 = "screen-0"
    SCREEN_1 = "screen-1"
    SCREEN_2 = "screen-2"
    SCREEN_3 = "screen-3"
    SCREEN_4 = "screen-4"
    SCREEN_5 = "screen-5"
    SCREEN_6 = "screen-6"
    SCREEN_7 = "screen-7"


class ComputerMouseButton(StrEnum):
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"


class ComputerScrollDirection(StrEnum):
    UP = "up"
    DOWN = "down"


class TemplateStatus(StrEnum):
    PENDING = "pending"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class TemplateInclude(StrEnum):
    DOCKERFILE = "dockerfile"


class DiskKind(StrEnum):
    S3 = "s3"


class DiskMountStatus(StrEnum):
    PENDING = "pending"
    MOUNTED = "mounted"
    ERROR = "error"
    UNMOUNTING = "unmounting"


class ManagedProcessWaitScope(StrEnum):
    LEADER = "leader"
    TREE = "tree"


def _json(
    name: str,
    *,
    omit_default: bool = False,
    default: Any = MISSING,
    default_factory: Any = MISSING,
):
    kwargs: dict[str, Any] = {
        "metadata": {"json": name, "omit_default": omit_default}
    }
    if default is not MISSING:
        kwargs["default"] = default
    if default_factory is not MISSING:
        kwargs["default_factory"] = default_factory
    return field(**kwargs)


@dataclass(slots=True)
class Model:
    """Provide JSON conversion for CreateOS wire-contract dataclasses."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Build a typed model from a JSON-compatible dictionary."""
        hints = get_type_hints(cls)
        values = {}
        for item in fields(cls):
            key = item.metadata.get("json", item.name)
            if key in data:
                values[item.name] = _convert(
                    data[key], hints.get(item.name, Any)
                )
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """Convert this model into its JSON-compatible wire form."""
        result = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if value is None:
                continue
            if item.metadata.get("omit_default"):
                if item.default is not MISSING and value == item.default:
                    continue
                if (
                    item.default_factory is not MISSING
                    and value == item.default_factory()
                ):
                    continue
            result[item.metadata.get("json", item.name)] = _wire(value)
        return result


def _wire(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Model):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _convert(value: Any, annotation: Any) -> Any:
    if value is None or annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        non_none = next((arg for arg in args if arg is not type(None)), Any)
        return _convert(value, non_none)
    if origin is list:
        return [_convert(item, args[0]) for item in value]
    if origin is dict:
        return dict(value)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)
    if annotation is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(annotation, type) and issubclass(annotation, Model):
        return annotation.from_dict(value)
    return value


TModel = TypeVar("TModel", bound=Model)


# Request contracts
@dataclass(slots=True)
class NetworkEntry(Model):
    id: str = ""


@dataclass(slots=True)
class DiskAttachment(Model):
    disk_id: str = _json("disk_id", default="")
    mount_path: str = _json("mount_path", default="")
    sub_path: str = _json("sub_path", omit_default=True, default="")


@dataclass(slots=True)
class CreateSandboxRequest(Model):
    shape: str = ""
    rootfs: str = _json("rootfs", omit_default=True, default="")
    name: str = _json("name", omit_default=True, default="")
    networks: list[NetworkEntry] = _json(
        "networks", omit_default=True, default_factory=list
    )
    disk_mib: int = _json("disk_mib", omit_default=True, default=0)
    egress_rules: list[str] = _json(
        "egress", omit_default=True, default_factory=list
    )
    environment_variables: dict[str, str] = _json(
        "envs", omit_default=True, default_factory=dict
    )
    ssh_public_keys: list[str] = _json(
        "ssh_pubkeys", omit_default=True, default_factory=list
    )
    host_id: str = _json("host_id", omit_default=True, default="")
    node_selector: dict[str, str] = _json(
        "node_selector", omit_default=True, default_factory=dict
    )
    ingress_enabled: bool = _json(
        "ingress_enabled", omit_default=True, default=False
    )
    disks: list[DiskAttachment] = _json(
        "disks", omit_default=True, default_factory=list
    )
    region: str = _json("region", omit_default=True, default="")
    auto_pause_after_seconds: int = _json(
        "auto_pause_after_seconds", omit_default=True, default=0
    )


@dataclass(slots=True)
class ForkSandboxRequest(Model):
    start_paused: bool = _json("start_paused", omit_default=True, default=False)
    ssh_public_keys: list[str] | None = _json("ssh_pubkeys", default=None)
    egress_rules: list[str] | None = _json("egress", default=None)
    ingress_enabled: bool | None = _json("ingress_enabled", default=None)
    environment_variables: dict[str, str] | None = _json("envs", default=None)


@dataclass(slots=True)
class RunCommandRequest(Model):
    command: str = _json("cmd", default="")
    arguments: list[str] = _json(
        "args", omit_default=True, default_factory=list
    )
    standard_input: str = _json("stdin", omit_default=True, default="")
    environment_variables: dict[str, str] = _json(
        "env", omit_default=True, default_factory=dict
    )
    stream: bool = _json("stream", omit_default=True, default=False)


@dataclass(slots=True)
class PTYSize(Model):
    rows: int = _json("rows", omit_default=True, default=0)
    cols: int = _json("cols", omit_default=True, default=0)


@dataclass(slots=True)
class ManagedProcessCreateRequest(Model):
    command: str = _json("cmd", omit_default=True, default="")
    arguments: list[str] = _json(
        "args", omit_default=True, default_factory=list
    )
    working_directory: str = _json("cwd", omit_default=True, default="")
    environment_variables: dict[str, str] = _json(
        "env", omit_default=True, default_factory=dict
    )
    pty: PTYSize | None = None


@dataclass(slots=True)
class ComputerPoint(Model):
    x: int = 0
    y: int = 0


@dataclass(slots=True)
class ComputerClickRequest(Model):
    button: ComputerMouseButton | None = None
    x: int | None = None
    y: int | None = None
    count: int = _json("count", omit_default=True, default=0)


@dataclass(slots=True)
class ComputerScrollRequest(Model):
    direction: ComputerScrollDirection | None = None
    amount: int = _json("amount", omit_default=True, default=0)


@dataclass(slots=True)
class ComputerDragRequest(Model):
    from_: ComputerPoint = _json("from", default_factory=ComputerPoint)
    to: ComputerPoint = field(default_factory=ComputerPoint)


@dataclass(slots=True)
class ComputerButtonRequest(Model):
    button: ComputerMouseButton | None = None


@dataclass(slots=True)
class ComputerTypeRequest(Model):
    text: str = ""
    delay_in_ms: int = _json("delay_in_ms", omit_default=True, default=0)


@dataclass(slots=True)
class ComputerOpenRequest(Model):
    target: str = ""


@dataclass(slots=True)
class ComputerLaunchRequest(Model):
    application: str = ""
    uri: str = _json("uri", omit_default=True, default="")


@dataclass(slots=True)
class ComputerWindowMoveRequest(Model):
    x: int = 0
    y: int = 0


@dataclass(slots=True)
class ComputerWindowResizeRequest(Model):
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class ComputerCreateScreenRequest(Model):
    width: int = _json("width", omit_default=True, default=0)
    height: int = _json("height", omit_default=True, default=0)


@dataclass(slots=True)
class TemplateCreateRequest(Model):
    name: str = ""
    dockerfile: str = ""
    base: str = _json("base", omit_default=True, default="")


@dataclass(slots=True)
class DiskConfig(Model):
    bucket: str = ""
    endpoint: str = ""
    region: str = _json("region", omit_default=True, default="")
    use_path_style: bool = _json(
        "use_path_style", omit_default=True, default=False
    )


@dataclass(slots=True)
class DiskCredentials(Model):
    access_key: str = _json("access_key", default="")
    secret_key: str = _json("secret_key", default="")


@dataclass(slots=True)
class DiskCreateRequest(Model):
    name: str = ""
    kind: DiskKind = DiskKind.S3
    config: DiskConfig = field(default_factory=DiskConfig)
    credentials: DiskCredentials = field(default_factory=DiskCredentials)


@dataclass(slots=True)
class NetworkCreateRequest(Model):
    name: str = ""


# Options
@dataclass(slots=True)
class RetryOptions:
    max_retries: int = 2
    base_delay: float = 0.5
    max_delay: float = 30.0


@dataclass(slots=True)
class RequestOptions:
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    retry: RetryOptions | None = None
    disable_retry: bool = False


@dataclass(slots=True)
class ListSandboxesOptions(RequestOptions):
    limit: int = 0
    status: SandboxStatus | None = None


@dataclass(slots=True)
class ExecOptions(RequestOptions):
    standard_input: str | None = None
    environment_variables: dict[str, str] | None = None


@dataclass(slots=True)
class ManagedProcessConnectOptions(RequestOptions):
    after_sequence: int = 0


@dataclass(slots=True)
class ManagedProcessWaitOptions(RequestOptions):
    scope: ManagedProcessWaitScope | None = None
    wait_timeout: float | None = None


@dataclass(slots=True)
class ManagedProcessDeleteOptions(RequestOptions):
    grace_period: float | None = None


@dataclass(slots=True)
class ComputerScreenOptions(RequestOptions):
    screen_id: ComputerScreenID | None = None


@dataclass(slots=True)
class ComputerScreenshotOptions(ComputerScreenOptions):
    window_id: str = ""
    x: int | None = None
    y: int | None = None
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class ComputerListWindowsOptions(ComputerScreenOptions):
    application: str = ""


@dataclass(slots=True)
class GetTemplateOptions(RequestOptions):
    include: TemplateInclude | None = None


@dataclass(slots=True)
class TemplateLogsOptions(RequestOptions):
    attempt: int = 0


@dataclass(slots=True)
class AttachDiskOptions:
    disk_id: str
    mount_path: str
    sub_path: str = ""


@dataclass(slots=True)
class DetachDiskOptions:
    disk_id: str
    mount_path: str = ""


@dataclass(slots=True)
class WaitOptions:
    timeout: float = 120.0
    request: RequestOptions = field(default_factory=RequestOptions)


@dataclass(slots=True)
class PaginationOptions:
    limit: int = 0
    offset: int = 0


# Response contracts
@dataclass(slots=True)
class Shape(Model):
    id: str = ""
    vcpu: int = 0
    memory_mib: int = _json("mem_mib", default=0)
    default_disk_mib: int = _json("default_disk_mib", default=0)
    cpu_quota_pct: int = _json("cpu_quota_pct", default=0)


@dataclass(slots=True)
class RootFSEntry(Model):
    name: str = ""
    description: str | None = None
    deprecated: bool = False
    successor: str | None = None


@dataclass(slots=True)
class RootFSData(Model):
    root_file_systems: list[str] = _json("rootfs", default_factory=list)
    default: str = ""
    entries: list[RootFSEntry] = field(default_factory=list)


@dataclass(slots=True)
class HostPublic(Model):
    id: str = ""
    status: HostStatus = HostStatus.ACTIVE
    free_memory_mib: int = _json("free_mib", default=0)
    sandbox_count: int = _json("vm_count", default=0)
    root_file_systems: list[str] = _json("rootfses", default_factory=list)


@dataclass(slots=True)
class CreateSandboxResponse(Model):
    id: str
    status: SandboxStatus
    name: str | None = None
    ip_address: str = _json("ip", default="")
    shape: str = ""
    rootfs: str | None = None
    vcpu: int = 0
    memory_mib: int = _json("mem_mib", default=0)
    disk_mib: int = _json("disk_mib", default=0)
    spawn_milliseconds: float = _json("spawn_ms", default=0.0)
    egress_rules: list[str] = _json("egress", default_factory=list)
    bandwidth_quota_bytes: int = 0
    ingress_url_template: str = ""


@dataclass(slots=True)
class Sandbox(Model):
    id: str
    status: SandboxStatus
    ip_address: str | None = _json("ip", default=None)
    vcpu: int = 0
    memory_mib: int = _json("mem_mib", default=0)
    disk_mib: int = _json("disk_mib", default=0)
    created_at: datetime | None = _json("created_at", default=None)
    ingress_enabled: bool = False
    ingress_url_template: str = ""
    name: str | None = None
    running_at: datetime | None = None
    destroyed_at: datetime | None = None
    spawn_milliseconds: float = _json("spawn_ms", default=0.0)
    shape: str = ""
    rootfs: str | None = None
    region: str = ""
    egress_rules: list[str] = _json("egress", default_factory=list)
    environment_variables: list[str] = _json("envs", default_factory=list)
    ssh_public_keys: list[str] = _json("ssh_pubkeys", default_factory=list)
    created_by: str = ""
    bandwidth_ingress_bytes: int = 0
    paused_at: datetime | None = None
    last_resumed_at: datetime | None = None
    forked_from: str | None = None
    auto_pause_after_seconds: int | None = None


@dataclass(slots=True)
class SandboxAccessTokenCreateResponse(Model):
    """Plaintext delegated token returned only on creation or rotation."""

    token: str
    enabled: bool
    created_at: datetime
    rotated_at: datetime | None = None


@dataclass(slots=True)
class SandboxAccessTokenMetadata(Model):
    """Token state without the plaintext credential."""

    enabled: bool
    token_hint: str | None = None
    created_at: datetime | None = None
    rotated_at: datetime | None = None


@dataclass(slots=True)
class CommandResult(Model):
    standard_output: str = _json("stdout", default="")
    standard_error: str = _json("stderr", default="")
    exit_code: int = 0
    error_message: str = _json("error", default="")


@dataclass(slots=True)
class RunCommandResponse(Model):
    result: CommandResult = field(default_factory=CommandResult)
    execution_milliseconds: float = _json("exec_ms", default=0.0)


@dataclass(slots=True)
class DestroyedResponse(Model):
    id: str
    status: SandboxStatus


@dataclass(slots=True)
class CommandStreamEvent(Model):
    type: ExecStreamEventType = ExecStreamEventType.HEARTBEAT
    data: str = ""
    exit_code: int | None = _json("exitCode", default=None)
    error_message: str = _json("message", default="")


@dataclass(slots=True)
class ManagedProcessOutputWindow(Model):
    oldest_sequence: int = _json("oldest_seq", default=0)
    newest_sequence: int = _json("newest_seq", default=0)
    bytes: int = 0


@dataclass(slots=True)
class ManagedProcessForeground(Model):
    process_id: int = _json("pid", default=0)
    command: str = _json("cmd", default="")
    arguments: list[str] = _json("args", default_factory=list)


@dataclass(slots=True)
class ManagedProcess(Model):
    process_id: str = ""
    kind: ManagedProcessKind = ManagedProcessKind.PROCESS
    pid: int = 0
    state: ManagedProcessState = ManagedProcessState.STARTING
    leader_exited: bool = False
    tree_exited: bool = False
    created_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    signal: str | None = None
    command: str = _json("cmd", default="")
    arguments: list[str] = _json("args", default_factory=list)
    working_directory: str = _json("cwd", default="")
    foreground: ManagedProcessForeground | None = None
    output: ManagedProcessOutputWindow = field(
        default_factory=ManagedProcessOutputWindow
    )


@dataclass(slots=True)
class ManagedProcessConnectEvent(Model):
    type: ManagedProcessConnectEventType = (
        ManagedProcessConnectEventType.HEARTBEAT
    )
    sequence: int = _json("seq", default=0)
    stream: ManagedProcessStream | None = None
    data: bytes = b""
    exit_code: int | None = _json("exitCode", default=None)
    signal: str | None = None
    error_message: str = _json("message", default="")
    oldest_available_sequence: int = _json("oldestAvailableSeq", default=0)


@dataclass(slots=True)
class ComputerScreenGeometry(Model):
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class ComputerClipboard(Model):
    text: str = ""


@dataclass(slots=True)
class ComputerWindow(Model):
    id: str = ""
    title: str = ""


@dataclass(slots=True)
class ComputerWindowGeometry(Model):
    id: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    screen: int = 0


@dataclass(slots=True)
class ComputerScreen(Model):
    screen_id: ComputerScreenID = ComputerScreenID.SCREEN_0
    display: str = ""
    width: int = 0
    height: int = 0
    vnc_port: int = 0
    novnc_port: int = 0


@dataclass(slots=True)
class ComputerScreenConnection(Model):
    screen_id: ComputerScreenID = ComputerScreenID.SCREEN_0
    port: int = 0
    path: str = ""
    token: str = ""
    expires_at: datetime | None = None
    url: str = ""


@dataclass(slots=True)
class EgressView(Model):
    id: str = ""
    egress_rules: list[str] = _json("egress", default_factory=list)


@dataclass(slots=True)
class BandwidthView(Model):
    id: str = ""
    quota_bytes: int = 0
    used_bytes: int = 0
    ingress_bytes: int = 0
    remaining_bytes: int = 0
    capped: bool = False


@dataclass(slots=True)
class ResizeSandboxResponse(Model):
    id: str = ""
    disk_mib: int = 0


@dataclass(slots=True)
class WhoAmIStats(Model):
    running: int = 0
    paused: int = 0
    other: int = 0
    total: int = 0


@dataclass(slots=True)
class WhoAmI(Model):
    user_id: str = ""
    stats: WhoAmIStats = field(default_factory=WhoAmIStats)


@dataclass(slots=True)
class Template(Model):
    id: str = ""
    name: str = ""
    base: str = ""
    status: TemplateStatus = TemplateStatus.PENDING
    ext4_size_bytes: int = 0
    created_at: datetime | None = None
    built_at: datetime | None = None
    dockerfile: str = ""


@dataclass(slots=True)
class TemplateLogEvent(Model):
    timestamp: datetime | None = _json("ts", default=None)
    level: str = ""
    line: str = ""
    attempt: int = 0
    final: bool = False
    status: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Build a log event while preserving unknown event fields."""
        known = {"ts", "level", "line", "attempt", "final", "status"}
        value = super().from_dict(data)
        value.extra = {
            key: item for key, item in data.items() if key not in known
        }
        return value


@dataclass(slots=True)
class Disk(Model):
    id: str = ""
    name: str = ""
    kind: DiskKind = DiskKind.S3
    config: DiskConfig = field(default_factory=DiskConfig)
    created_at: datetime | None = None


@dataclass(slots=True)
class SandboxDisk(Model):
    disk_id: str = ""
    name: str = ""
    kind: DiskKind = DiskKind.S3
    config: DiskConfig = field(default_factory=DiskConfig)
    mount_path: str = ""
    sub_path: str = ""
    mount_status: DiskMountStatus = DiskMountStatus.PENDING
    mount_error: str = ""


@dataclass(slots=True)
class NetworkMember(Model):
    sandbox_id: str = ""
    status: str = ""
    ip_address: str = _json("ip", default="")
    name: str = ""


@dataclass(slots=True)
class Network(Model):
    id: str = ""
    name: str = ""
    created_at: datetime | None = None
    member_count: int = 0
    members: list[NetworkMember] = field(default_factory=list)


@dataclass(slots=True)
class Health(Model):
    up: bool = False


@dataclass(slots=True)
class Readiness(Model):
    ready: bool = False
    reason: str = ""
    scheduler_last_ok_milliseconds_ago: int = _json(
        "scheduler_last_ok_ms_ago", default=0
    )
