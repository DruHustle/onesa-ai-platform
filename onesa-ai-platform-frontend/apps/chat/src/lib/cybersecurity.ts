import { call } from "./api";

export type Asset = {
  id: string;
  name: string;
  identity: string;
  zone: string;
  criticality: string;
  details: {
    review_note?: string;
    twin?: { asset_id: string; component_id: string | null } | null;
  };
};
export type Inventory = {
  id: string;
  producer: string;
  sha256: string;
  created_at: string;
  details: {
    mode: string;
    matching: string;
    exploitability: string;
    document: {
      components: {
        name: string;
        version?: string;
        type: string;
        "bom-ref": string;
      }[];
      vulnerabilities: {
        id: string;
        ratings?: { severity: string; score?: number }[];
        affects: { ref: string }[];
      }[];
    };
  };
};
export type ReportMetadata = {
  id: string;
  producer: string;
  sha256: string;
  profile: string;
  component_count: number;
  advisory_count: number;
  mode: string;
};
export type Source = {
  id: string;
  name: string;
  namespace: string;
  scope: string;
  revoked_at: string | null;
  config: { modes: string[]; expected_interval_seconds: number };
};
export type SecurityEvent = {
  id: string;
  source_id: string;
  asset_id: string | null;
  event_type: string;
  mode: string;
  occurred_at: string;
  created_at: string;
  expires_at: string;
  sha256: string;
  wire: {
    summary: string;
    quality: string;
    attributes: Record<string, unknown>;
  };
  provenance: { basis: string; late: boolean };
};
export type Finding = {
  id: string;
  source_id: string;
  asset_id: string | null;
  rule: string;
  rule_version: string;
  severity: string;
  confidence: string;
  priority: number;
  mode: string;
  run_id: string;
  first_seen: string;
  last_seen: string;
  occurrences: number;
  details: {
    explanation: string;
    expected: unknown;
    observed: unknown;
    evidence: SecurityEvent[];
    priority_formula: string;
    quality: string[];
  };
};
export type Investigation = {
  id: string;
  title: string;
  finding_id: string;
  status: string;
  priority: number;
  revision: number;
  updated_at: string;
  sha256: string;
  acceptance_until: string | null;
  snapshot: { finding: Finding };
};
export type Action = {
  id: string;
  kind: string;
  created_at: string;
  details: { note?: string; review?: string; evidence?: SecurityEvent[] };
};
export type Workspace = {
  assets: Asset[];
  sources: Source[];
  events: SecurityEvent[];
  findings: Finding[];
  investigations: Omit<Investigation, "snapshot">[];
  source_health: {
    source_id: string;
    state: string;
    last_received: string | null;
    reported_state: string | null;
  }[];
  policies: {
    id: string;
    source_id: string;
    version: number;
    sha256: string;
    config: Record<string, unknown>;
  }[];
  baselines: {
    id: string;
    source_id: string;
    revision: string;
    config: Record<string, unknown>;
  }[];
  mappings: {
    id: string;
    source_id: string;
    asset_id: string;
    external_namespace: string;
    external_asset: string;
    external_component: string;
  }[];
  coverage: {
    assets: number;
    assessed: number;
    stale: number;
    unknown: number;
    definition: string;
    window: string;
  };
  control_coverage: {
    assessed: number;
    unknown: number;
    stale: number;
    denominator: number;
    definition: string;
    mode: string;
    evaluated_at: string;
    by_asset: {
      asset_id: string;
      controls: {
        control: string;
        state: string;
        eligible_observations: number;
      }[];
    }[];
  };
  counts: {
    findings: number;
    affected_assets: number;
    open_investigations: number;
  };
  bounded: { events: number; findings: number; investigations: number };
};
export type CaseDetail = {
  investigation: Investigation;
  evidence: {
    history: Action[];
    history_next: string | null;
    checklist: string[];
    missing: string[];
    finding: Finding;
  };
  acceptance_expired: boolean;
  summaries: {
    id: string;
    created_at: string;
    sha256: string;
    result: Record<string, unknown>;
  }[];
};
export type Readiness = {
  enabled: boolean;
  operator: boolean;
  native_capture_configured: boolean;
  ai_enabled: boolean;
  demo_enabled: boolean;
  scope: string;
};
export async function security<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return (await call(`/cybersecurity${path}`, method, body, signal)).json();
}
export const eventExample = (namespace: string, mode: string) => ({
  events: [
    {
      schemaVersion: "ot-security-evidence/v1",
      producerNamespace: namespace,
      sourceEventId: crypto.randomUUID(),
      occurredAt: new Date().toISOString(),
      mode,
      ...(mode === "simulated"
        ? { scenarioRunId: "explicit-local-demonstration" }
        : mode === "replay"
          ? { replayRunId: "explicit-local-replay" }
          : {}),
      eventType: "collector.health",
      assetRef: null,
      summary: "Explicitly supplied collector coverage observation",
      quality: "uncertain",
      producerVersion: "1.0.0",
      attributes: { state: "degraded", expectedIntervalSeconds: 60 },
    },
  ],
});
