/**
 * Hand-written TypeScript mirrors of `contracts/schemas/*` and `services/api/src/ikip_api/schemas.py`.
 *
 * These are kept in lock-step with the Python models by field name and enum value, the same
 * way `ikip_contracts.models` is a hand-written mirror of the JSON Schemas until codegen is
 * wired up (see `web/README.md` → "Generated types" and `justfile` → `codegen`). Do not rename
 * a field here without renaming it in `contracts/schemas` and `ikip_contracts` first.
 */

// --- enums (contracts/schemas, packages/ikip-contracts/src/ikip_contracts/enums.py) ---

export type StatementClass =
  | "historical_observation"
  | "recommendation"
  | "approved_procedure"
  | "completed_work"
  | "inference";

export type Authority = "approved" | "draft" | "superseded" | "withdrawn" | "unknown";

export type RetrievalChannel = "exact" | "lexical" | "semantic" | "relationship" | "shape";

export type Outcome = "answered" | "abstained";

export type AbstentionReason =
  | "insufficient"
  | "ambiguous"
  | "stale"
  | "conflicting"
  | "unauthorized_scope"
  | "unavailable";

// --- request shapes (services/api/src/ikip_api/schemas.py: QueryRequest, RevokeRequest) ---

export interface QueryRequest {
  question: string;
  asset_ids?: string[];
  sites?: string[];
}

export interface RevokeRequest {
  document_id: string;
}

// --- /search response (schemas.py: EvidenceView, SearchResponse) ---

export interface EvidenceView {
  evidence_id: string;
  document_id: string;
  text: string;
  authority: Authority;
  retrieval_score: number | null;
  retrieved_by: RetrievalChannel | null;
}

export interface SearchResponse {
  evidence: EvidenceView[];
  count: number;
}

// --- /answer response (contracts/schemas/answer.schema.json, ikip_contracts.models.Answer) ---

export interface Citation {
  claim_id: string;
  evidence_ids: string[];
  statement_class: StatementClass;
  source_coordinates?: Record<string, unknown> | null;
  authority?: Authority | null;
}

export interface Claim {
  claim_id: string;
  text: string;
  citation: Citation;
}

export interface Conflict {
  description?: string | null;
  [key: string]: unknown;
}

export interface Abstention {
  reason: AbstentionReason;
  message: string;
  suggested_action?: string | null;
}

export interface Answer {
  request_id: string;
  outcome: Outcome;
  config_version: string;
  claims?: Claim[] | null;
  conflicts?: Conflict[] | null;
  abstention?: Abstention | null;
}

// --- /admin/acl/revoke response ---

export interface RevokeResponse {
  document_id: string;
  revoked: boolean;
}

// --- /healthz response ---

export interface HealthResponse {
  status: string;
}

// --- dev identity (services/api/src/ikip_api/identity.py: dev_identity) ---
// The API refuses to authenticate anyone unless IKIP_DEV_AUTH=1 is set on the server; these
// headers are read only under that dev stub and must never exist in a production build.

export interface DevIdentity {
  subject: string;
  roles: string[];
  sites: string[];
  verified: boolean;
}
