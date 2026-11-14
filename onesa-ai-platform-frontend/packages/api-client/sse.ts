/** Bounded, runtime-validated chat protocol. UTF-8 and CRLF may span chunks. */
export type ModelIdentity = { backend: string; model_identifier: string; real_inference: boolean };
export type ChatEvent =
  | { kind: "message_start"; conversation_id: string; run_id: string }
  | { kind: "content_delta"; text: string }
  | { kind: "message_end"; model: ModelIdentity }
  | { kind: "error"; message: string };
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
export async function* chatEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let pending = "", total = 0, ended = false, started = false;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (pending.length > 1024 * 1024) throw new Error("Stream frame exceeds limit");
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(pending))) {
        const frame = pending.slice(0, match.index);
        pending = pending.slice(match.index + match[0].length);
        const lines = frame.split(/\r?\n/);
        const kind = lines.find(line => line.startsWith("event:"))?.slice(6).trim();
        const data = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).replace(/^ /, "")).join("\n");
        if (!data) continue; // SSE heartbeat/comments.
        if (ended) throw new Error("Event after terminal stream event");
        const parsed: unknown = JSON.parse(data);
        if (!object(parsed)) throw new Error("Invalid stream payload");
        if (kind === "message_start") {
          if (started || typeof parsed.conversation_id !== "string" || typeof parsed.run_id !== "string") throw new Error("Invalid stream start");
          started = true;
          yield { kind, conversation_id: parsed.conversation_id, run_id: parsed.run_id };
        } else if (kind === "content_delta") {
          if (!started || typeof parsed.text !== "string") throw new Error("Invalid stream delta");
          total += parsed.text.length;
          if (total > 128000) throw new Error("Stream text exceeds limit");
          yield { kind, text: parsed.text };
        } else if (kind === "message_end") {
          const model = parsed.model;
          if (!started || typeof parsed.message_id !== "string" || !object(model) || typeof model.backend !== "string" || typeof model.model_identifier !== "string" || typeof model.real_inference !== "boolean") throw new Error("Invalid stream completion");
          ended = true;
          yield { kind, model: { backend: model.backend, model_identifier: model.model_identifier, real_inference: model.real_inference } };
        } else if (kind === "error") {
          if (typeof parsed.code !== "string" || typeof parsed.message !== "string" || typeof parsed.request_id !== "string") throw new Error("Invalid stream error");
          ended = true;
          yield { kind, message: parsed.message };
        } else throw new Error("Unknown stream event");
      }
      if (done) break;
    }
    if (!ended || pending.trim()) throw new Error("Response interrupted. You can retry.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
