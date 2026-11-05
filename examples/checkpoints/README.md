# Checkpoints

Capture a directory, modify it, restore its earlier contents, and remove the
checkpoint.

```sh
export CREATEOS_API_KEY="your-api-key"
python examples/checkpoints/main.py
```

The example creates live resources and cleans them up when it finishes. Stop
all writers before creating or restoring a checkpoint.
