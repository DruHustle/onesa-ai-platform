import { z } from 'zod';

// Production destinations are source-owned. No QR code, model text, deep link,
// remote config or user-entered URL can select a credential destination.
export const ORIGIN = 'https://platform.onesa.eu';
export const NATIVE_ORIGIN = 'onesaai://native';
export const CALLBACK = 'onesaai://auth/callback';
export const APP_ID = 'eu.onesa.aiplatform';
export const KNOWLEDGE_DOCUMENTS = '/knowledge/documents';
export const KNOWLEDGE_SEARCH = '/knowledge/search';
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const opaque = /^[A-Za-z0-9_-]{43,128}$/;
export const userSchema = z.object({ id: z.string().uuid(), email: z.string().email(), display_name: z.string().max(80) });
export const credentialSchema = z.object({
  access_token: z.string().min(43).max(256).regex(/^[A-Za-z0-9_.-]+$/),
  expires_at: z.string().datetime({ offset: true }), user: userSchema,
});
export type Credential = z.infer<typeof credentialSchema>;
export type User = z.infer<typeof userSchema>;

export function authorization(value: unknown) {
  const data = z.object({ request_id: z.string().uuid(), authorize_url: z.string() }).parse(value);
  const url = new URL(data.authorize_url);
  if (url.origin !== ORIGIN || url.pathname !== '/auth/native' || url.username || url.password || url.hash ||
      url.searchParams.getAll('request').length !== 1 || url.searchParams.get('request') !== data.request_id ||
      [...url.searchParams.keys()].some(key => key !== 'request')) throw new Error('Sign-in destination was rejected.');
  return data;
}

export function callbackCode(value: string, state: string): string {
  const url = new URL(value);
  if (url.protocol !== 'onesaai:' || url.hostname !== 'auth' || url.pathname !== '/callback' || url.port ||
      url.username || url.password || url.hash || !opaque.test(state) ||
      [...url.searchParams.keys()].some(key => key !== 'state' && key !== 'code') ||
      url.searchParams.getAll('state').length !== 1 || url.searchParams.get('state') !== state ||
      url.searchParams.getAll('code').length !== 1 || !opaque.test(url.searchParams.get('code') || '')) {
    throw new Error('Sign-in response was rejected. Please start again.');
  }
  return url.searchParams.get('code')!;
}

export function apiURL(path: string): string {
  // This client has no admin, machine-control, provider or arbitrary URL route.
  const [pathname, query = ''] = path.split('?');
  const safe = /^\/(?:auth\/native\/(?:start|token|logout)|auth\/me|models|conversations(?:\/[0-9a-f-]{36}(?:\/cancel)?)?|chat\/completions|knowledge\/(?:documents|search)|agents\/(?:tools|runs)|travel\/trips(?:\/[0-9a-f-]{36})?)$/i;
  if (!safe.test(pathname) || path.includes('#') || path.split('?').length > 2 ||
      (query && !/^limit=(?:[1-9]|[1-9][0-9]|100)(?:&offset=\d{1,7})?$/.test(query))) throw new Error('Unsupported native API route.');
  return `${ORIGIN}/api/v1${path}`;
}

export function validCredential(value: unknown, now = Date.now()): Credential {
  const data = credentialSchema.parse(value);
  if (Date.parse(data.expires_at) <= now) throw new Error('Your session has expired.');
  return data;
}

export function messageText(content: Record<string, unknown>): string {
  return typeof content.text === 'string' ? content.text : '';
}

export const conversationSchema = z.object({ id: z.string().uuid(), title: z.string().max(200), selected_model_id: z.string(), created_at: z.string(), updated_at: z.string() });
export const conversationListSchema = z.object({ items: z.array(conversationSchema).max(100), total: z.number().nonnegative(), next_cursor: z.string().nullable().optional() });
export const detailSchema = z.object({ conversation: conversationSchema, messages: z.array(z.object({ id: z.string().uuid(), role: z.enum(['user', 'assistant', 'system']), content: z.record(z.string(), z.unknown()), status: z.enum(['completed', 'failed', 'cancelled']), sequence: z.number() })) });
export type Conversation = z.infer<typeof conversationSchema>;
export type Detail = z.infer<typeof detailSchema>;
export const modelsSchema = z.object({ items: z.array(z.object({ id: z.literal('default'), name: z.string(), backend: z.enum(['mock', 'ollama', 'vllm', 'llamacpp', 'cloudflare']), model_identifier: z.string(), real_inference: z.boolean() })).max(10) });
export type Model = z.infer<typeof modelsSchema>['items'][number];
export const documentSchema = z.object({ id: z.string().uuid(), title: z.string(), media_type: z.string(), embedding_version: z.string(), created_at: z.string() });
export const documentsSchema = z.object({ items: z.array(documentSchema).max(100), next_cursor: z.string().nullable().optional() });
export const searchSchema = z.object({ backend: z.enum(['lexical', 'http', 'cloudflare']), sources: z.array(z.object({ document_id: z.string().uuid(), title: z.string(), chunk: z.number(), text: z.string(), distance: z.number(), embedding_version: z.string() })) });
export const agentRunsSchema = z.object({ items: z.array(z.object({ id: z.string().uuid(), goal: z.string(), status: z.enum(['running', 'completed', 'failed', 'cancelled']), steps: z.array(z.record(z.string(), z.unknown())), created_at: z.string() })), next_cursor: z.string().nullable().optional() });
export const toolsSchema = z.object({ items: z.array(z.object({ name: z.string(), effect: z.enum(['local computation', 'read-only owned evidence']) })) });
export const tripSchema = z.object({ id: z.string().uuid(), destination: z.string(), duration: z.number().int().min(1).max(14), budget: z.number(), currency: z.string(), revision: z.number(), notice: z.string(), live_data_verified: z.literal(false), itinerary: z.object({ backend: z.enum(['mock', 'ollama', 'vllm', 'llamacpp', 'cloudflare']), assumptions: z.array(z.string()), days: z.array(z.object({ day: z.number(), activities: z.array(z.object({ title: z.string(), notes: z.string() })) })) }) });
export const tripsSchema = z.object({ items: z.array(tripSchema), next_cursor: z.string().nullable().optional() });
