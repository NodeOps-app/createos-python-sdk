"""Start a web server and fetch it through public sandbox ingress."""

from __future__ import annotations

import httpx

from createos import (
    Client,
    CreateSandboxRequest,
    ManagedProcessCreateRequest,
    RunCommandRequest,
)


def main() -> None:
    """Create, verify, and destroy an ingress-enabled sandbox."""
    with Client() as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(
                shape="s-1vcpu-256mb",
                rootfs="devbox:1",
                ingress_enabled=True,
            )
        )
        print(f"created: {sandbox.id}")
        try:
            sandbox.run_command(
                RunCommandRequest(
                    command="mkdir",
                    arguments=["-p", "/srv"],
                )
            )
            sandbox.files.upload(
                "/srv/index.html",
                b"<h1>hello from CreateOS Sandbox preview URL</h1>",
            )
            sandbox.processes.create(
                ManagedProcessCreateRequest(
                    command="python3",
                    arguments=[
                        "-m",
                        "http.server",
                        "8080",
                        "--bind",
                        "0.0.0.0",
                    ],
                    working_directory="/srv",
                )
            )
            sandbox.wait_for_port(8080, timeout=10)
            preview_url = sandbox.preview_url(8080)
            print(f"URL: {preview_url}")

            # Preview ingress currently uses a self-signed certificate.
            with httpx.Client(verify=False, timeout=30) as http_client:
                response = http_client.get(preview_url)
                response.raise_for_status()
            print("--- response ---")
            print(response.text)
        finally:
            sandbox.destroy()
            print(f"destroyed: {sandbox.id}")


if __name__ == "__main__":
    main()
