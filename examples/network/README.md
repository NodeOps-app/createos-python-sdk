# Private overlay network

Create a private network, attach a sandbox, and verify the sandbox appears in
the network membership response.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/network/main.py
```

Cleanup detaches the sandbox before destroying it and deleting the network.
