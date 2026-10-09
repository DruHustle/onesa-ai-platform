# Streaming chat integration

POST /api/v1/chat/completions with conversation_id, content and stream=true. The response is Server-Sent Events: message_start, content_delta, message_end; error events indicate failed generation. Parse complete frames across arbitrary transport chunks. A stream closing without message_end is incomplete.

Stop or close the client connection to cancel. No successful partial assistant message is persisted. One active generation is allowed per conversation; retry only after its lease is released or expires. Successful completions may include safe model provenance and actual reported usage/timing; unknown token counts are null.

See [examples](examples.md) and [authentication](authentication.md).
