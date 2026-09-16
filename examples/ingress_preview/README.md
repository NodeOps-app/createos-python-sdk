# Ingress preview

Start an HTTP server inside a sandbox, obtain its public preview URL, and fetch
the uploaded page through ingress.

```sh
python -m pip install createos-sandbox
export CREATEOS_API_KEY="your-api-key"
python examples/ingress_preview/main.py
```

The example disables TLS verification only for the preview request because the
preview endpoint currently uses a self-signed certificate. Do not copy that
setting into general-purpose HTTP clients.
