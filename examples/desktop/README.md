# Desktop and noVNC

Create a graphical sandbox and exercise screen discovery, screenshots, cursor
movement, clipboard access, browser launch, and temporary noVNC connectivity.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/desktop/main.py
```

The example uses the `desktop:1` root filesystem and a larger sandbox shape.
The printed noVNC URL contains a short-lived access token; treat it as
sensitive and do not publish it.
