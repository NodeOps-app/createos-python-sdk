"""Capture a reusable disk snapshot and restore a sandbox from it."""

import os
import time

from createos import (
    Client,
    CreateSandboxRequest,
    CreateSnapshotRequest,
    Snapshot,
    SnapshotStatus,
    SnapshotType,
)


def wait_until_ready(client: Client, snapshot_id: str) -> Snapshot:
    """Poll a snapshot for up to five minutes."""
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        snapshot = client.snapshots.get(snapshot_id)
        if snapshot.status is SnapshotStatus.READY:
            return snapshot
        if snapshot.status is SnapshotStatus.FAILED:
            raise RuntimeError(f"snapshot {snapshot_id} failed")
        time.sleep(1)
    raise TimeoutError(f"snapshot {snapshot_id} did not become ready")


def main() -> None:
    """Create, capture, restore, and clean up live resources."""
    with Client(api_key=os.environ["CREATEOS_API_KEY"]) as client:
        source = client.create_sandbox(
            CreateSandboxRequest(shape="s-1vcpu-1gb", rootfs="alpine:3.20")
        )
        snapshot = None
        restored = None
        try:
            snapshot = source.create_snapshot(
                CreateSnapshotRequest(
                    type=SnapshotType.DISK, name="configured-workspace"
                )
            )
            snapshot = wait_until_ready(client, snapshot.id)
            restored = client.create_sandbox(
                CreateSandboxRequest(snapshot_id=snapshot.id)
            )
            print(f"restored sandbox {restored.id} from snapshot {snapshot.id}")
        finally:
            if restored is not None:
                restored.destroy()
            source.destroy()
            if snapshot is not None and snapshot.status in {
                SnapshotStatus.READY,
                SnapshotStatus.FAILED,
            }:
                client.snapshots.delete(snapshot.id)


if __name__ == "__main__":
    main()
