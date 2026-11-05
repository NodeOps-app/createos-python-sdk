"""Capture and restore local directory history inside one sandbox."""

import os

from createos import (
    Client,
    CreateCheckpointRequest,
    CreateSandboxRequest,
    RunCommandRequest,
)

CHECKPOINT_PATH = "/workspace/checkpoint-demo"


def command(sandbox, script: str):
    """Run a shell command inside the sandbox."""
    return sandbox.run_command(
        RunCommandRequest(command="sh", arguments=["-c", script])
    )


def main() -> None:
    """Create, checkpoint, restore, and clean up live resources."""
    with Client(api_key=os.environ["CREATEOS_API_KEY"]) as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(shape="s-1vcpu-1gb", rootfs="devbox:1")
        )
        checkpoint = None
        try:
            command(
                sandbox,
                f"mkdir -p {CHECKPOINT_PATH} && "
                f"printf 'version one' > {CHECKPOINT_PATH}/value",
            )
            checkpoint = sandbox.checkpoints.create(
                CreateCheckpointRequest(
                    path=CHECKPOINT_PATH, name="before-update"
                )
            )
            command(
                sandbox,
                f"printf 'version two' > {CHECKPOINT_PATH}/value",
            )
            sandbox.checkpoints.restore(checkpoint.id)
            result = command(sandbox, f"cat {CHECKPOINT_PATH}/value")
            print(f"restored {checkpoint.id}: {result.result.standard_output}")
        finally:
            if checkpoint is not None:
                sandbox.checkpoints.delete(checkpoint.id)
            sandbox.destroy()


if __name__ == "__main__":
    main()
