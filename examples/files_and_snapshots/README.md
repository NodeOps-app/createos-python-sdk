# Files and snapshots

Pause and fork a sandbox, then verify that the fork inherits the source
filesystem while later writes remain isolated from the source.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/files_and_snapshots/main.py
```

This example can take several minutes while the source and fork pause and
resume. Both sandboxes are destroyed during cleanup.
