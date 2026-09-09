"""Demonstrate copy-on-write sandbox snapshots and file divergence."""

from __future__ import annotations

from datetime import datetime, timezone

from createos import (
    Client,
    CreateSandboxRequest,
    ForkSandboxRequest,
    RunCommandRequest,
    WaitOptions,
)

_BASE_PATH = "/root/seed.txt"
_FORK_ONLY_PATH = "/root/fork-only.txt"


def _read_file(sandbox, path: str) -> str:
    """Read a sandbox file through command execution for demonstration."""
    response = sandbox.run_command(
        RunCommandRequest(
            command="sh",
            arguments=["-c", f"cat {path} 2>&1"],
        )
    )
    return response.result.standard_output.strip()


def main() -> None:
    """Fork a paused sandbox and verify filesystem isolation."""
    with Client() as client:
        base = client.create_sandbox(
            CreateSandboxRequest(
                shape="s-1vcpu-256mb",
                rootfs="devbox:1",
            )
        )
        print(f"base created: {base.id}")
        clone = None
        try:
            stamp = datetime.now(timezone.utc).isoformat()
            base.files.upload(
                _BASE_PATH,
                f"seed written at {stamp}\n".encode(),
            )
            print(f"wrote {_BASE_PATH}: {_read_file(base, _BASE_PATH)}")

            # Forking a paused machine captures a stable filesystem snapshot.
            print("pausing base...")
            base.pause().wait_until_paused(WaitOptions(timeout=600))
            print("base paused")

            print("forking base (start_paused=true)...")
            clone = base.fork(ForkSandboxRequest(start_paused=True))
            clone.wait_until_paused(WaitOptions(timeout=600))
            print(
                f"fork paused: {clone.id} "
                f"(forked_from={clone.data.forked_from or ''})"
            )

            print("resuming fork...")
            clone.resume().wait_until_running(WaitOptions(timeout=300))
            print(f"fork running: {clone.id}")
            print(
                f"fork inherits {_BASE_PATH}: {_read_file(clone, _BASE_PATH)}"
            )

            clone.files.upload(
                _FORK_ONLY_PATH,
                f"written only in fork at {stamp}\n".encode(),
            )
            print(
                f"fork wrote {_FORK_ONLY_PATH}: "
                f"{_read_file(clone, _FORK_ONLY_PATH)}"
            )

            print("resuming base...")
            base.resume().wait_until_running(WaitOptions(timeout=300))
            missing = base.run_command(
                RunCommandRequest(
                    command="test",
                    arguments=["!", "-e", _FORK_ONLY_PATH],
                )
            )
            if missing.result.exit_code:
                raise RuntimeError("base unexpectedly contains fork-only file")
            print("base does not see fork-only file")
            print(
                f"base still has {_BASE_PATH}: {_read_file(base, _BASE_PATH)}"
            )
        finally:
            # Delete the dependent fork before its source sandbox.
            if clone is not None:
                clone.destroy()
                print(f"destroyed fork: {clone.id}")
            base.destroy()
            print(f"destroyed base: {base.id}")


if __name__ == "__main__":
    main()
