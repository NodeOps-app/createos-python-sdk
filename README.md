# CreateOS Python SDK

Launch an isolated cloud sandbox, run real commands, stream output, move files,
open a preview URL, and tear everything down from Python.

## Your first sandbox

```sh
pip install createos
```

Python 3.10 or newer is required.

```python
from createos import Client, CreateSandboxRequest, RunCommandRequest


with Client(api_key="your-api-key") as client:
    sandbox = client.create_sandbox(
        CreateSandboxRequest(
            name="hello-python",
            shape="s-4vcpu-4gb",
            rootfs="devbox:1",
        )
    )
    try:
        response = sandbox.run_command(
            RunCommandRequest(
                command="sh",
                arguments=[
                    "-c",
                    'printf "Python says hello from $(uname -m)\\n"',
                ],
            )
        )
        print(response.result.standard_output, end="")
    finally:
        sandbox.destroy()
```

```text
Python says hello from x86_64
```

Do not commit a real API key to source control; inject it through your
application's secret manager. You can configure the endpoint and default
request timeout when constructing the client:

```python
client = Client(
    api_key=api_key,
    base_url="http://localhost:8080",
    timeout=30,
)
```

As an alternative, `Client()` reads `CREATEOS_SANDBOX_API_KEY` and
`CREATEOS_SANDBOX_BASE_URL`. Explicit constructor arguments take precedence.

## Documentation

- [CreateOS Sandbox overview](https://nodeops.network/createos/docs/Sandbox/Overview)
  explains the sandbox model, lifecycle, networking, storage, and isolation.
- [CreateOS Sandbox documentation](https://nodeops.network/createos/docs)
  contains the REST API reference and product guides.
- [CreateOS Go SDK](https://github.com/NodeOps-app/createos-go-sdk) provides the
  same sandbox capabilities for Go applications.
- [CreateOS TypeScript SDK](https://github.com/NodeOps-app/createos-sandbox-sdk)
  provides the same sandbox capabilities for JavaScript and TypeScript
  applications.
- [Runnable examples](#examples) demonstrate complete SDK workflows.
- The public Python API is typed and documented with Python docstrings.
- [Contributing guide](CONTRIBUTING.md) documents development checks and commit
  conventions.

## Stream output as it happens

Long-running commands do not need to disappear behind a buffered HTTP call:

```python
import sys

from createos import ExecStreamEventType, RunCommandRequest


request = RunCommandRequest(
    command="sh",
    arguments=[
        "-c",
        'for n in 1 2 3; do echo "step $n"; sleep 1; done',
    ],
)

with sandbox.stream_command(request) as stream:
    for event in stream:
        if event.type is ExecStreamEventType.STDOUT:
            print(event.data, end="")
        elif event.type is ExecStreamEventType.STDERR:
            print(event.data, end="", file=sys.stderr)
        elif event.type is ExecStreamEventType.EXIT:
            print(f"exit code: {event.exit_code}")
```

Stopping early is safe: leaving the `with` block closes the response body and
releases the underlying HTTP connection.

## Move files without shell escaping

```python
sandbox.files.upload(
    "/workspace/config.json",
    b'{"mode":"production"}',
)

with sandbox.files.download("/workspace/config.json") as download:
    contents = download.read()
```

`upload()` also accepts a binary file-like object, allowing large files to be
transferred without reading them all into memory first.

## Keep a process alive after disconnecting

Managed processes are resources rather than fragile terminal sessions. Start
one, reconnect from its output sequence, send input or signals, and wait for
either the leader or its complete process tree:

```python
from createos import (
    ManagedProcessCreateRequest,
    ManagedProcessWaitOptions,
    ManagedProcessWaitScope,
)


process = sandbox.processes.create(
    ManagedProcessCreateRequest(
        command="sh",
        arguments=["-c", "sleep 1; echo managed process finished"],
    )
)

finished = sandbox.processes.wait(
    process.process_id,
    ManagedProcessWaitOptions(
        scope=ManagedProcessWaitScope.TREE,
        wait_timeout=30,
    ),
)
```

## Turn a service into a URL

Create a sandbox with ingress enabled, wait for the server to listen, then ask
the instance for its public URL:

```python
from createos import CreateSandboxRequest, ManagedProcessCreateRequest


sandbox = client.create_sandbox(
    CreateSandboxRequest(
        shape="s-4vcpu-4gb",
        rootfs="devbox:1",
        ingress_enabled=True,
    )
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
    )
)

sandbox.wait_for_port(8080, host="127.0.0.1", timeout=15)
print(sandbox.preview_url(8080))
```

## Everything is already connected

Account-level services are initialized by `Client`:

```python
templates = client.templates
networks = client.networks
disks = client.disks

custom_templates = templates.list()
print(
    f"{len(custom_templates)} templates ready; "
    f"networks={type(networks).__name__} disks={type(disks).__name__}"
)
```

Instance-level services are initialized when a sandbox handle is created or
retrieved:

```python
sandbox.files
sandbox.processes
sandbox.computer.mouse
sandbox.computer.keyboard
sandbox.computer.windows
sandbox.computer.screens
```

## Connect sandboxes on a private network

Create an overlay network, attach a running sandbox, and inspect the resulting
membership. Cleanup runs in reverse order, so the sandbox detaches before the
network is deleted:

```python
from createos import NetworkCreateRequest


network = client.networks.create(NetworkCreateRequest(name="agent-mesh"))
try:
    sandbox.attach_network(network.id)
    try:
        connected = client.networks.get(network.id)
        for member in connected.members:
            print(
                f"sandbox={member.sandbox_id} "
                f"private-ip={member.ip_address} "
                f"status={member.status}"
            )
    finally:
        sandbox.detach_network(network.id)
finally:
    client.networks.delete(network.id)
```

## Lifecycle reads like the domain

```python
sandbox.pause().wait_until_paused()

clone = sandbox.fork()
try:
    sandbox.resume().wait_until_running()
finally:
    clone.destroy()

sandbox.destroy()
```

The `SandboxInstance` handle safely caches the latest server projection.
Lifecycle mutations and `refresh()` update it, while `id`, `name`, `status`,
`ip_address`, and `data` provide safe reads.

## Errors stay inspectable

```python
from createos import APIError, OperationTimeout


try:
    sandbox.wait_until_running()
except APIError as error:
    print(
        f"HTTP {error.status_code}, code={error.code}, "
        f"request={error.request_id}"
    )
except OperationTimeout:
    # A lifecycle or readiness wait exhausted its budget.
    pass
```

GET, HEAD, PUT, and DELETE requests are retried for transient network failures
and retryable server responses. HTTP 429 and 503 are retried for every method.
Configure the client with `RetryOptions`, or disable retries for one request
with `RequestOptions(disable_retry=True)`.

## Examples

Runnable examples live under [`examples/`](examples/):

- [Hello world](examples/hello_world.py)
- [HTTP execution server](examples/execution_server/README.md)
- [Command streaming](examples/command_streaming.py)
- [Files and snapshots](examples/files_and_snapshots.py)
- [Ingress preview](examples/ingress_preview.py)
- [Private overlay network](examples/network.py)
- [Custom template](examples/custom_template.py)
- [Managed process lifecycle](examples/managed_process.py)
- [Desktop and noVNC](examples/desktop.py)

Together these examples cover command execution, file transfer, streaming,
ingress, snapshots, networking, templates, managed processes, and desktop use.

## Development

Create a virtual environment and install the development dependencies:

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Run the same checks used while developing the SDK:

```sh
.venv/bin/ruff format --check src tests examples
.venv/bin/ruff check src tests examples
.venv/bin/mypy src/createos --ignore-missing-imports
.venv/bin/pytest --cov=createos --cov-fail-under=70
```

The project follows the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
Formatting, import ordering, public docstrings, and static analysis are enforced
through the project configuration.

GitHub Actions runs these quality checks, tests Python 3.10 through 3.14, builds
both package distributions, and verifies that the generated wheel imports.

Commits follow Conventional Commits. See
[CONTRIBUTING.md](CONTRIBUTING.md) for accepted types, examples, and the checks
to run before opening a pull request.

## Package layout

```text
src/createos/client.py      client configuration and account-level operations
src/createos/instance.py    stateful sandbox lifecycle and command operations
src/createos/services.py    files, processes, desktop, templates, disks, networks
src/createos/models.py      public requests, responses, options, and enums
src/createos/_transport.py  HTTP, authentication, retries, and JSend handling
src/createos/_streams.py    NDJSON, SSE, command, process, and binary streams
examples/                   runnable Python programs
tests/                      mocked API contract tests
```

## About CreateOS

[CreateOS](https://createos.sh) is an execution and governance platform for AI
agents and applications. Learn more about isolated Firecracker-based workloads
on the [CreateOS Sandbox product page](https://createos.sh/products/sandbox).

## License

This SDK is available under the [MIT License](LICENSE).
