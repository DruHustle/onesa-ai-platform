# Developer quickstart

Requires Docker Compose. Run the following once in a fresh checkout; bootstrap refuses to overwrite private configuration.

```bash
python3 scripts/bootstrap_env.py
make up
```

Open the configured loopback application address (default localhost:3000). If changing the port, change both ONESA_CHAT_PORT and ONESA_PUBLIC_ORIGIN. Expected result: database migrations complete, API becomes ready, and the sign-in screen opens. Fresh environments use clearly labelled mock inference.

Create an account using synthetic development data, open Chat and send a first message. The inference badge distinguishes mock from real generation.

```bash
make check
make frontend-check
make down
```

Tests validate development behavior. down preserves data volumes. See [troubleshooting](troubleshooting.md) and [tutorials](tutorials.md).
