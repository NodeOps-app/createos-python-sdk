# Managed processes

Exercise persistent pipe and PTY processes, including input, output replay,
terminal resize, waiting, and process-tree termination.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/managed_process/main.py
```

The example verifies environment overrides, standard output and error,
replayed frames, PTY output, and complete process-tree termination.
