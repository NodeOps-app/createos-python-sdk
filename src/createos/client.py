"""CreateOS control-plane client."""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from ._transport import Transport
from ._version import __version__
from .instance import SandboxInstance
from .models import (
    CreateSandboxRequest,
    CreateSandboxResponse,
    Health,
    HostPublic,
    ListSandboxesOptions,
    PaginationOptions,
    Readiness,
    RequestOptions,
    RetryOptions,
    RootFSData,
    Sandbox,
    Shape,
    WhoAmI,
)
from .services import (
    DisksService,
    NetworksService,
    TemplatesService,
    _fetch_all,
    _many,
    _one,
    _request_options,
)


class Client:
    """Authenticated entry point to the CreateOS Sandbox API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 60.0,
        user_agent: str = f"createos-python-sdk/{__version__}",
        retry: RetryOptions | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._transport = Transport(
            base_url=(
                base_url
                or os.getenv("CREATEOS_SANDBOX_BASE_URL")
                or "https://api.sb.createos.sh"
            ).strip(),
            api_key=(
                api_key
                if api_key is not None
                else os.getenv("CREATEOS_API_KEY", "")
            ),
            timeout=timeout,
            user_agent=user_agent,
            retry=retry or RetryOptions(),
            http_client=http_client,
        )
        self.templates = TemplatesService(self._transport)
        self.networks = NetworksService(self._transport)
        self.disks = DisksService(self._transport)

    @property
    def base_url(self) -> str:
        """Return the configured control-plane base URL."""
        return self._transport.base_url

    def close(self) -> None:
        """Close HTTP resources owned by this client."""
        self._transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def health(self) -> Health:
        """Return the unauthenticated control-plane liveness state."""
        return _one(
            Health, self._transport.request("GET", "/healthz", skip_auth=True)
        )

    healthz = health

    def readiness(self) -> Readiness:
        """Return the unauthenticated control-plane readiness state."""
        path = "/readyz"
        response = self._transport.request_raw(
            "GET",
            path,
            skip_auth=True,
            options=RequestOptions(disable_retry=True),
        )
        try:
            if response.status_code not in {200, 503}:
                self._transport._raise_for_status(response, "GET", path)
            try:
                envelope = response.json()
                data = envelope.get("data")
                if isinstance(data, dict):
                    return _one(Readiness, data)
            except ValueError:
                pass
            return Readiness(ready=response.status_code == 200)
        finally:
            response.close()

    readyz = readiness

    def who_am_i(self) -> WhoAmI:
        """Return the identity associated with the configured API key."""
        return _one(WhoAmI, self._transport.request("GET", "/v1/whoami"))

    def create_sandbox(
        self,
        request: CreateSandboxRequest,
        options: RequestOptions | None = None,
    ) -> SandboxInstance:
        """Create a running sandbox and return its connected handle."""
        data = self._transport.request(
            "POST", "/v1/sandboxes", body=request, options=options
        )
        created = _one(CreateSandboxResponse, data)
        sandbox = Sandbox(
            id=created.id,
            status=created.status,
            ip_address=created.ip_address,
            vcpu=created.vcpu,
            memory_mib=created.memory_mib,
            disk_mib=created.disk_mib,
            ingress_enabled=request.ingress_enabled,
            ingress_url_template=created.ingress_url_template,
            name=created.name,
            spawn_milliseconds=created.spawn_milliseconds,
            shape=created.shape,
            rootfs=created.rootfs,
            egress_rules=created.egress_rules,
        )
        return SandboxInstance(self._transport, sandbox)

    def get_sandbox(self, sandbox_id: str) -> SandboxInstance:
        """Return a connected handle for a sandbox ID."""
        data = self._transport.request(
            "GET", f"/v1/sandboxes/{quote(sandbox_id, safe='')}"
        )
        return SandboxInstance(self._transport, _one(Sandbox, data))

    def get_sandbox_by_ip(self, ip_address: str) -> SandboxInstance:
        """Return a connected handle for a sandbox private IP address."""
        data = self._transport.request(
            "GET", f"/v1/sandboxes/by-ip/{quote(ip_address, safe='')}"
        )
        return SandboxInstance(self._transport, _one(Sandbox, data))

    def list_sandboxes(
        self, options: ListSandboxesOptions | None = None
    ) -> list[SandboxInstance]:
        """Return sandbox handles visible to the caller."""
        options = options or ListSandboxesOptions()
        params = {"status": str(options.status)} if options.status else {}
        items: list[Sandbox] = []
        offset = 0
        while options.limit <= 0 or len(items) < options.limit:
            page_size = (
                min(500, options.limit - len(items)) if options.limit else 500
            )
            page_params = {**params, "limit": page_size, "offset": offset}
            data = self._transport.request(
                "GET",
                "/v1/sandboxes",
                params=page_params,
                options=_request_options(options),
            )
            page = _many(Sandbox, data)
            items.extend(page)
            total = (
                data.get("pagination", {}).get("total")
                if isinstance(data, dict)
                else None
            )
            if not page or total is None or offset + len(page) >= total:
                break
            offset += len(page)
        return [
            SandboxInstance(self._transport, item)
            for item in items[: options.limit or None]
        ]

    def list_shapes(self) -> list[Shape]:
        """Return available CPU, memory, and disk sizing presets."""
        return _fetch_all(
            self._transport,
            "/v1/shapes",
            Shape,
            PaginationOptions(),
            legacy_key="shapes",
            skip_auth=True,
        )

    def list_root_file_systems(self) -> RootFSData:
        """Return the built-in root filesystem catalog."""
        return _one(
            RootFSData,
            self._transport.request("GET", "/v1/rootfs", skip_auth=True),
        )

    def list_hosts(self) -> list[HostPublic]:
        """Return the administrator-visible worker host projection."""
        return _fetch_all(
            self._transport, "/v1/hosts", HostPublic, PaginationOptions()
        )


CreateOS = Client
