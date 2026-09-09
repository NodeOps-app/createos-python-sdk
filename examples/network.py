"""Connect a sandbox to a private overlay network."""

from __future__ import annotations

import time

from createos import Client, CreateSandboxRequest, NetworkCreateRequest


def main() -> None:
    """Create a network and verify sandbox membership."""
    with Client() as client:
        network = client.networks.create(
            NetworkCreateRequest(name=f"python-sdk-{time.time_ns()}")
        )
        print(f"created network: {network.id}")
        sandbox = None
        attached = False
        try:
            sandbox = client.create_sandbox(
                CreateSandboxRequest(
                    shape="s-1vcpu-1gb",
                    rootfs="devbox:1",
                )
            )
            print(f"created sandbox: {sandbox.id}")
            sandbox.attach_network(network.id)
            attached = True

            connected = client.networks.get(network.id)
            member = next(
                (
                    item
                    for item in connected.members
                    if item.sandbox_id == sandbox.id
                ),
                None,
            )
            if member is None:
                raise RuntimeError(
                    f"sandbox {sandbox.id} was not found in {network.id}"
                )
            print(
                f"verified member: sandbox={member.sandbox_id} "
                f"ip={member.ip_address} status={member.status}"
            )
        finally:
            if sandbox is not None:
                if attached:
                    sandbox.detach_network(network.id)
                    print(f"detached network: {network.id}")
                sandbox.destroy()
                print(f"destroyed sandbox: {sandbox.id}")
            client.networks.delete(network.id)
            print(f"deleted network: {network.id}")


if __name__ == "__main__":
    main()
