/**
 * Client for services/api (ikip_api.app:create_app). Only the four endpoints that service
 * actually implements are called here — /healthz, /search, /answer, /admin/acl/revoke.
 *
 * The wider contracts/openapi/api.v1.yaml (`/api/v1/query`, `/citations/{claimId}/source`,
 * `/feedback`, bearer-JWT auth) describes the target production gateway, which is not wired
 * up in this codebase yet — see services/gateway (prompt isolation only, no HTTP surface) and
 * services/api/src/ikip_api/identity.py (dev header stub only). This client intentionally
 * matches what is actually running today rather than the aspirational spec, so nothing here
 * silently breaks when pointed at the real dev server.
 *
 * In dev (`npm run dev`) requests go to `/api/*`, which vite.config.ts proxies to the FastAPI
 * server with no CORS involved. In a production build, set VITE_API_BASE_URL to the API's
 * origin directly — that path requires the backend to send CORS headers, which is a backend
 * change out of scope here; document it rather than assume it.
 */
import type {
  Answer,
  DevIdentity,
  HealthResponse,
  QueryRequest,
  RevokeRequest,
  RevokeResponse,
  SearchResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(
      typeof detail === "string"
        ? detail
        : (detail as { detail?: string } | undefined)?.detail ?? `Request failed (${status})`
    );
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Builds the X-Dev-* headers the dev identity stub reads. See identity.py for the contract. */
function identityHeaders(identity: DevIdentity): HeadersInit {
  return {
    "X-Dev-Subject": identity.subject || "dev-user",
    "X-Dev-Roles": identity.roles.join(","),
    "X-Dev-Sites": identity.sites.join(","),
    "X-Dev-Verified": identity.verified ? "1" : "0",
  };
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; identity?: DevIdentity } = {}
): Promise<T> {
  const { method = "GET", body, identity } = options;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(identity ? identityHeaders(identity) : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    // Network-level failure — the API is unreachable (not started, wrong proxy target, etc).
    throw new ApiError(0, `Cannot reach the API at ${BASE_URL}${path}. Is it running?`);
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }
  return payload as T;
}

export const api = {
  healthz: () => request<HealthResponse>("/healthz"),

  search: (query: QueryRequest, identity: DevIdentity) =>
    request<SearchResponse>("/search", { method: "POST", body: query, identity }),

  answer: (query: QueryRequest, identity: DevIdentity) =>
    request<Answer>("/answer", { method: "POST", body: query, identity }),

  revokeAcl: (req: RevokeRequest, identity: DevIdentity) =>
    request<RevokeResponse>("/admin/acl/revoke", { method: "POST", body: req, identity }),
};
