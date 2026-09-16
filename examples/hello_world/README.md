# Hello world

Create a sandbox, print its Linux system information, and destroy it.

```sh
python -m pip install createos-sandbox
export CREATEOS_API_KEY="your-api-key"
python examples/hello_world/main.py
```

The sandbox is destroyed in a `finally` block, including when command execution
fails.
