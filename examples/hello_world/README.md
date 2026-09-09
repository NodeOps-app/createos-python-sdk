# Hello world

Create a sandbox, print its Linux system information, and destroy it.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/hello_world/main.py
```

The sandbox is destroyed in a `finally` block, including when command execution
fails.
