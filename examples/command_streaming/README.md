# Command streaming

Upload a Python program and print its standard output as the sandbox produces
it. The example also handles standard error, heartbeats, agent errors, and the
final exit event.

```sh
python -m pip install createos-sandbox
export CREATEOS_SANDBOX_API_KEY="your-api-key"
python examples/command_streaming/main.py
```

The command prints five numbered results before the sandbox is destroyed.
