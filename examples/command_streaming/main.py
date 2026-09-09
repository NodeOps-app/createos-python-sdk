"""Upload a Python program and print its output as it runs."""

from __future__ import annotations

import sys

from createos import (
    Client,
    CreateSandboxRequest,
    ExecStreamEventType,
    RunCommandRequest,
)

_SCRIPT = """import time

for number in range(1, 6):
    print(f"result {number}", flush=True)
    time.sleep(1)
"""


def main() -> None:
    """Create a sandbox and stream a program's output."""
    with Client() as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(
                shape="s-1vcpu-1gb",
                rootfs="devbox:1",
            )
        )
        print(f"created: {sandbox.id}")
        try:
            sandbox.files.upload("/tmp/script.py", _SCRIPT.encode())
            request = RunCommandRequest(
                command="python3",
                arguments=["/tmp/script.py"],
            )
            print("--- streaming output ---")
            with sandbox.stream_command(request) as stream:
                for event in stream:
                    if event.type is ExecStreamEventType.STDOUT:
                        print(event.data, end="")
                    elif event.type is ExecStreamEventType.STDERR:
                        print(event.data, end="", file=sys.stderr)
                    elif event.type is ExecStreamEventType.ERROR:
                        print(
                            f"agent error: {event.error_message}",
                            file=sys.stderr,
                        )
                    elif event.type is ExecStreamEventType.EXIT:
                        print(f"(exited {event.exit_code})")
        finally:
            sandbox.destroy()
            print("destroyed")


if __name__ == "__main__":
    main()
