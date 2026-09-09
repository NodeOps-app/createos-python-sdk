"""Build a Docker-enabled template and run containers in its sandbox."""

from __future__ import annotations

import sys
import time

from createos import (
    Client,
    CreateSandboxRequest,
    ExecOptions,
    RequestOptions,
    RunCommandRequest,
    TemplateCreateRequest,
    TemplateLogsOptions,
    TemplateStatus,
)

_SHAPE = "s-1vcpu-1gb"
_DOCKERFILE = """FROM nodeops/sandbox:debian

RUN apt-get update -qq \\
 && apt-get install -y --no-install-recommends curl ca-certificates \\
 && curl -fsSL https://get.docker.com | sh \\
 && rm -rf /var/lib/apt/lists/*
"""


def _wait_for_template(client: Client, template_id: str) -> None:
    """Poll until a template is ready or reaches a terminal state."""
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        template = client.templates.get(template_id)
        if template.status is TemplateStatus.READY:
            return
        if template.status is TemplateStatus.FAILED:
            raise RuntimeError("template build failed; see logs above")
        if template.status not in {
            TemplateStatus.PENDING,
            TemplateStatus.BUILDING,
        }:
            raise RuntimeError(
                f"unexpected template status {template.status!r}"
            )
        time.sleep(2)
    raise TimeoutError("template did not become ready within 10 minutes")


def _wait_for_docker(sandbox) -> None:
    """Wait until the Docker daemon accepts commands in the sandbox."""
    for _ in range(30):
        result = sandbox.run_command(
            RunCommandRequest(
                command="docker",
                arguments=["info", "--format", "{{.ServerVersion}}"],
            ),
            ExecOptions(timeout=5),
        )
        if result.result.exit_code == 0:
            version = result.result.standard_output.strip()
            print(f"      dockerd ready (server version: {version})")
            return
        time.sleep(2)
    raise TimeoutError("dockerd did not start within 60 seconds")


def main() -> None:
    """Build and exercise a temporary Docker-enabled root filesystem."""
    with Client() as client:
        name = f"docker-ce-{time.time_ns()}"
        print(f"[1/5] submitting template build: {name}")
        template = client.templates.create(
            TemplateCreateRequest(name=name, dockerfile=_DOCKERFILE)
        )
        print(f"      template id: {template.id} status: {template.status}")
        sandbox = None
        try:
            print("[2/5] streaming build logs...")
            try:
                with client.templates.follow_logs(
                    template.id,
                    TemplateLogsOptions(timeout=600),
                ) as stream:
                    for event in stream:
                        if event.line:
                            print(event.line)
                        if event.final:
                            print(f"      build finished: {event.status}")
                            break
            except Exception as error:  # Log streaming is optional.
                print(
                    f"build log stream unavailable: {error}",
                    file=sys.stderr,
                )
            _wait_for_template(client, template.id)
            print(f"      template ready: {template.id}")

            print(
                f"[3/5] creating sandbox "
                f"(shape={_SHAPE}, rootfs={template.id})..."
            )
            sandbox = client.create_sandbox(
                CreateSandboxRequest(shape=_SHAPE, rootfs=template.id),
                RequestOptions(timeout=120),
            )
            print(f"      sandbox created: {sandbox.id}")

            print("[4/5] starting dockerd...")
            sandbox.shell("nohup setsid dockerd > /var/log/dockerd.log 2>&1 &")
            _wait_for_docker(sandbox)

            print("[5/5] running containers...")
            commands = [
                (
                    "docker run hello-world",
                    ["run", "--rm", "hello-world"],
                    120,
                ),
                (
                    "docker run alpine",
                    [
                        "run",
                        "--rm",
                        "alpine",
                        "sh",
                        "-c",
                        "echo hello from alpine && cat /etc/alpine-release",
                    ],
                    60,
                ),
                ("docker images", ["images"], 60),
            ]
            for title, arguments, timeout in commands:
                print(f"\n-- {title} --")
                response = sandbox.run_command(
                    RunCommandRequest(
                        command="docker",
                        arguments=arguments,
                    ),
                    ExecOptions(timeout=timeout),
                )
                if response.result.exit_code:
                    raise RuntimeError(
                        f"{title} exited with status "
                        f"{response.result.exit_code}: "
                        f"{response.result.standard_error.strip()}"
                    )
                print(response.result.standard_output.strip())
        finally:
            # A built template can be deleted after its sandbox is destroyed.
            if sandbox is not None:
                sandbox.destroy()
                print(f"destroyed sandbox: {sandbox.id}")
            client.templates.delete(template.id)
            print(f"deleted template: {template.id}")


if __name__ == "__main__":
    main()
