# Chat streaming

POST `/api/v1/chat/completions` accepts conversation_id, content, model_id (`default`),
stream (default true), and optional document_ids (max 20). Cookie/Origin/CSRF required.
Nonstream mode retains message_id/content/model_id/sources and adds model/metrics after persistence.
Streaming is text/event-stream with JSON data and these ordered event types:

| Event | Fields | Meaning |
| --- | --- | --- |
| message_start | conversation_id, run_id, sources, model | User turn/run committed; retrieved source evidence |
| content_delta | text | Zero or more ordered text deltas |
| message_end | message_id, model, metrics | Complete assistant committed; terminal success |
| error | code, message, request_id | Terminal generation failure; no message_end |

Usage is reported only when provided by the server: input_tokens/output_tokens remain null
otherwise (including mock). Metrics include total generation latency, first nonempty delta
and output tokens divided by total request generation time, not isolated decode throughput.
Existing run token fields and assistant JSONB inference metadata preserve successful provenance.
Safe model metadata reports backend, configured identifier/context/modalities/quantization/revision;
public alias remains default. Private URLs, keys and absolute artifact paths are omitted.

Errors before streaming use HTTP errors; failures after headers use error frames. Client
disconnect cancels and releases the lease, preserving the user turn but no successful
partial assistant. Actual socket-disconnect tests verify this behavior. Frontend aborts
fetch for Stop, labels interrupted content, and reloads persisted history. Concurrent
requests on the same conversation get 409. Character/history caps bound context; the
real serving backend retains token-level context validation.
