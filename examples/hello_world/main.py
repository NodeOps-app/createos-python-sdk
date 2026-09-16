"""Create a sandbox, run a command, and destroy the sandbox."""

import os

from createos import Client, CreateSandboxRequest, RunCommandRequest


def main() -> None:
    """Create a sandbox, run one command, and clean it up."""
    with Client(api_key=os.environ["CREATEOS_API_KEY"]) as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(
                name="hello-python",
                shape="s-4vcpu-4gb",
                rootfs="devbox:1",
            )
        )
        try:
            response = sandbox.run_command(
                RunCommandRequest(command="sh", arguments=["-c", "uname -a"])
            )
            print(response.result.standard_output, end="")
        finally:
            sandbox.destroy()


if __name__ == "__main__":
    main()
