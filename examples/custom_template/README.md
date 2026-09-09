# Custom template

Build a Docker-enabled root filesystem, create a sandbox from it, start the
Docker daemon, and run `hello-world` and Alpine containers.

```sh
export CREATEOS_SANDBOX_API_KEY="your-api-key"
.venv/bin/python examples/custom_template/main.py
```

The template build can take several minutes and downloads operating system
packages and container images. Cleanup destroys the sandbox before deleting
the template.
