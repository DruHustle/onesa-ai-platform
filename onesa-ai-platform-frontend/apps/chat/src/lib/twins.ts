import { call, csrf, ApiError } from "./api";

export type Component = {
  id: string;
  template_component_id: string;
  name: string;
  parent_id: string | null;
  external_id: string;
  semantic_reference?: string;
};
export type TwinAsset = {
  id: string;
  name: string;
  serial: string;
  template_id: string;
  active_model_id: string | null;
  revision: number;
  definition: {
    components: Component[];
    relationships: { source: string; target: string; kind: string }[];
    stage: string;
    review_model_id?: string;
    source_import_id?: string;
    demo?: boolean;
    external_id?: string;
    aas_id?: string;
  };
};
export type Model = {
  id: string;
  file_id: string;
  template_id: string;
  definition: {
    mappings: { node: string; component_id: string }[];
    nodes: { ref: string; name: string }[];
    unit: string;
    meters_per_unit: number;
    frame: string;
    transform: number[];
    provenance: string;
    sha256: string;
    byte_length: number;
  };
};
export type Reading = {
  id: string;
  source_id: string;
  component_id: string;
  tag: string;
  value: number;
  unit: string;
  mode: string;
  quality: string;
  observed_at: string;
  ingested_at: string;
};
export type Signal = {
  rule_state: "alarm" | "normal" | "unknown";
  source_id: string;
  source_name: string;
  binding: {
    tag: string;
    component_id: string;
    metric: string;
    unit: string;
    high: number | null;
    hysteresis: number;
    stale_seconds: number;
  };
  freshness: string;
  connection: string;
  reading: Reading | null;
};
export type Note = {
  id: string;
  snapshot_url?: string;
  component_id: string;
  kind: string;
  created_at: string;
  payload: {
    text?: string;
    camera?: number[];
    title?: string;
    checklist?: string[];
    evidence?: Evidence;
  };
};
export type Detail = {
  asset: TwinAsset;
  models: Model[];
  state: Signal[];
  documents: {
    document_id: string;
    component_id: string | null;
    title: string;
  }[];
  files: { id: string; filename: string; size: number }[];
  notes: Note[];
  sources: { id: string; name: string; revoked: boolean }[];
  mode: string;
};
export type History = {
  start: string;
  end: string;
  mode: string;
  readings: Reading[];
  events: {
    id: string;
    component_id: string;
    observed_at: string;
    kind: string;
    tag: string;
    value: number;
    unit: string;
    meaning: string;
  }[];
  truncated: boolean;
};
export type Evidence = {
  equipment: { id: string; name: string; serial: string };
  component: Component;
  facts: Signal[];
  history: History;
  documents: {
    document_id: string;
    title: string;
    chunk: number;
    text: string;
    anchor: string;
  }[];
  limitations: string[];
  next_inspection: string;
  viewer_actions: {
    action: "focus_component" | "highlight_components";
    component_ids: string[];
  }[];
  assistant: {
    status: string;
    text: string;
    hypotheses: { statement: string; document_id: string; quote: string }[];
  };
};
export type FilePreview = {
  id: string;
  filename: string;
  size: number;
  sha256: string;
  details: {
    format: string;
    nodes?: { ref: string; name: string; hint: string }[];
    name?: string;
    aas_id?: string;
    external_id?: string;
    geometry_status?: string;
    notice?: string;
    specification?: string;
    properties?: { id: string; value: string }[];
    references?: { id: string; path: string; status: string }[];
    unsupported?: { type: string; id: string }[];
    attachments?: { path: string; id: string; details: { format: string } }[];
    committed_asset_id?: string;
  };
};

export async function twin<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await call(
    `/twins${path}`,
    method,
    body,
    signal || AbortSignal.timeout(15000),
  );
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function uploadTwin(file: File): Promise<FilePreview> {
  if (file.size > 4 * 1024 * 1024)
    throw new Error("File limit is 4 MiB. Prepare a smaller GLB or package.");
  const data = new FormData();
  data.append("file", file);
  const response = await fetch("/api/v1/twins/files", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrf() },
    body: data,
    signal: AbortSignal.timeout(45000),
  });
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("onesa-session-expired"));
    const value = await response.json().catch(() => ({}));
    throw new ApiError(
      value.error?.message || "Upload failed",
      response.status,
      value.error?.code || "upload_failed",
    );
  }
  return response.json();
}
