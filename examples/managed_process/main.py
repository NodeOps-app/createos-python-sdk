"""Exercise managed pipe and PTY process lifecycles."""

from __future__ import annotations

from dataclasses import dataclass

from createos import (
    Client,
    CreateSandboxRequest,
    ManagedProcessConnectEventType,
    ManagedProcessConnectOptions,
    ManagedProcessCreateRequest,
    ManagedProcessDeleteOptions,
    ManagedProcessStream,
    ManagedProcessWaitOptions,
    ManagedProcessWaitScope,
    PTYSize,
)


@dataclass
class _Output:
    """Collect decoded process output and its replay position."""

    stdout: str = ""
    stderr: str = ""
    pty: str = ""
    last_sequence: int = 0
    data_frames: int = 0


def _collect(stream) -> _Output:
    """Consume a process stream and separate data by output channel."""
    output = _Output()
    with stream:
        for event in stream:
            if event.type is ManagedProcessConnectEventType.EXIT:
                return output
            if event.type is ManagedProcessConnectEventType.ERROR:
                raise RuntimeError(
                    event.error_message or "process stream reported an error"
                )
            if event.type is not ManagedProcessConnectEventType.DATA:
                continue
            value = event.data.decode(errors="replace")
            if event.stream is ManagedProcessStream.STDOUT:
                output.stdout += value
            elif event.stream is ManagedProcessStream.STDERR:
                output.stderr += value
            elif event.stream is ManagedProcessStream.PTY:
                output.pty += value
            output.last_sequence = max(output.last_sequence, event.sequence)
            output.data_frames += 1
    return output


def _indent(value: str) -> str:
    """Indent captured terminal output for readable example logs."""
    if not value:
        return "        (empty)"
    return "        " + value.replace("\n", "\n        ").rstrip()


def main() -> None:
    """Verify pipe input, replay, PTY resize, and termination."""
    with Client() as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(
                shape="s-1vcpu-1gb",
                rootfs="devbox:1",
                environment_variables={
                    "PROCESS_DEMO_BASE": "from-sandbox-env",
                    "PROCESS_DEMO_OVERRIDE": "declared-at-create",
                },
            )
        )
        print(f"created: {sandbox.id}")
        try:
            processes = sandbox.processes
            print("\n[1/4] pipe process with stdin/stdout/stderr...")
            script = "; ".join(
                [
                    "printf 'base:%s\\n' \"$PROCESS_DEMO_BASE\"",
                    "printf 'override:%s\\n' \"$PROCESS_DEMO_OVERRIDE\"",
                    "printf 'stderr:ready\\n' >&2",
                    "IFS= read -r line",
                    "printf 'stdin:%s\\n' \"$line\"",
                ]
            )
            pipe_process = processes.create(
                ManagedProcessCreateRequest(
                    command="/bin/sh",
                    arguments=["-c", script],
                    working_directory="/root",
                    environment_variables={
                        "PROCESS_DEMO_OVERRIDE": "from-process-env"
                    },
                )
            )
            print(f"      pipe: {pipe_process.process_id}")
            print(f"      listed processes: {len(processes.list())}")
            processes.input(
                pipe_process.process_id,
                "hello managed process\n",
            )
            processes.close_standard_input(pipe_process.process_id)
            pipe_done = processes.wait(
                pipe_process.process_id,
                ManagedProcessWaitOptions(
                    scope=ManagedProcessWaitScope.TREE,
                    wait_timeout=5,
                ),
            )
            print(f"      pipe exit: {pipe_done.exit_code}")
            pipe_output = _collect(processes.connect(pipe_process.process_id))
            print(f"      stdout:\n{_indent(pipe_output.stdout)}")
            print(f"      stderr:\n{_indent(pipe_output.stderr)}")

            print("\n[2/4] reconnect from output offset...")
            # Rewind one frame to prove that retained output is replayable.
            after = max(pipe_output.last_sequence - 1, 0)
            replay = _collect(
                processes.connect(
                    pipe_process.process_id,
                    ManagedProcessConnectOptions(after_sequence=after),
                )
            )
            print(
                f"      replayed data frames after sequence {after}: "
                f"{replay.data_frames}"
            )

            print("\n[3/4] interactive PTY shell...")
            pty_process = processes.create(
                ManagedProcessCreateRequest(
                    working_directory="/root",
                    pty=PTYSize(rows=24, cols=80),
                )
            )
            print(f"      PTY: {pty_process.process_id}")
            processes.input(
                pty_process.process_id,
                "echo terminal-ready; stty size\n",
            )
            processes.resize(
                pty_process.process_id,
                PTYSize(rows=32, cols=100),
            )
            processes.input(
                pty_process.process_id,
                "echo after-resize; stty size; exit\n",
            )
            pty_done = processes.wait(
                pty_process.process_id,
                ManagedProcessWaitOptions(
                    scope=ManagedProcessWaitScope.TREE,
                    wait_timeout=5,
                ),
            )
            print(f"      PTY exit: {pty_done.exit_code}")
            pty_output = _collect(processes.connect(pty_process.process_id))
            print(_indent(pty_output.pty))

            print("\n[4/4] terminate a long-running process tree...")
            long_running = processes.create(
                ManagedProcessCreateRequest(
                    command="/bin/sh",
                    arguments=["-c", "trap '' TERM; sleep 300 & wait"],
                )
            )
            terminated = processes.delete(
                long_running.process_id,
                ManagedProcessDeleteOptions(grace_period=0.1),
            )
            print(
                "      terminated: "
                f"leader_exited={terminated.leader_exited} "
                f"tree_exited={terminated.tree_exited}"
            )

            if "stdin:hello managed process" not in pipe_output.stdout:
                raise RuntimeError("pipe stdout did not include stdin echo")
            if not {"terminal-ready", "after-resize"}.issubset(
                pty_output.pty.split()
            ):
                raise RuntimeError("PTY output omitted command markers")
            if not terminated.tree_exited:
                raise RuntimeError("terminated process tree did not exit")
            print("\nverified managed pipe and PTY lifecycle")
        finally:
            sandbox.destroy()
            print("destroyed")


if __name__ == "__main__":
    main()
