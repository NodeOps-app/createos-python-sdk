# Reusable snapshots

Capture a reusable disk snapshot, wait for it to become ready, and restore a
new sandbox from it.

```sh
export CREATEOS_API_KEY="your-api-key"
python examples/reusable_snapshots/main.py
```

The example creates live resources and cleans them up when it finishes.
