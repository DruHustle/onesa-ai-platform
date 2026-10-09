# API integration guide

The implemented public application contract uses /api/v1. Consult the generated [API explorer](/api-explorer) for exact schemas and methods. Model discovery returns the stable default alias and safe backend metadata. Create an owned conversation before requesting chat completion. Mutations require session-bound CSRF and Origin.

Pagination is documented per endpoint; do not assume every list has cursor pagination. Error envelopes have code, message where supplied, and request_id; validation failures may use the FastAPI validation format. Handle 401/403, not-found, busy/conflict, validation, throttling and sanitized model-unavailable outcomes.

The explorer is read-only unless a loopback development environment is explicitly configured. No production keys or private model-server endpoints are included. See [streaming](streaming.md) and [examples](examples.md).
