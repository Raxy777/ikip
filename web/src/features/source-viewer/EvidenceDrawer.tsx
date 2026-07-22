import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { Citation, DevIdentity, EvidenceView, QueryRequest } from "../../lib/types";
import { AuthorityBadge } from "../../components/badges";
import { ErrorBanner } from "../../components/primitives";

interface Props {
  citation: Citation;
  query: QueryRequest;
  identity: DevIdentity;
  onClose: () => void;
}

/**
 * contracts/openapi/api.v1.yaml documents `GET /citations/{claimId}/source` re-checking
 * authorization because access may have changed since retrieval — but that endpoint isn't
 * implemented in services/api yet (only /search, /answer, /admin/acl/revoke are). Re-running
 * /search for the same query against the caller's *current* identity gets the same real
 * guarantee — a document revoked after the answer was generated will no longer come back —
 * without inventing a fake endpoint response.
 */
export function EvidenceDrawer({ citation, query, identity, onClose }: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [found, setFound] = useState<EvidenceView[]>([]);
  const [missingIds, setMissingIds] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    api
      .search(query, identity)
      .then((res) => {
        if (cancelled) return;
        const byId = new Map(res.evidence.map((e) => [e.evidence_id, e]));
        const present = citation.evidence_ids.map((id) => byId.get(id)).filter(Boolean) as EvidenceView[];
        const missing = citation.evidence_ids.filter((id) => !byId.has(id));
        setFound(present);
        setMissingIds(missing);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not re-check authorization.");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citation.claim_id]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Cited source">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>Cited source</h3>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>

        <p className="panel-desc" style={{ margin: 0 }}>
          Re-checking authorization now rather than showing what was cached at answer time —
          access may have changed since.
        </p>

        {status === "loading" && (
          <div className="status-line">
            <span className="spinner" /> Re-checking authorization…
          </div>
        )}

        {status === "error" && <ErrorBanner>{error}</ErrorBanner>}

        {status === "ready" && (
          <>
            {found.map((ev) => (
              <div className="evidence-card" key={ev.evidence_id}>
                <div className="evidence-meta">
                  <AuthorityBadge authority={ev.authority} />
                  <span>{ev.document_id}</span>
                  <span>{ev.evidence_id}</span>
                  {ev.retrieved_by && <span>via {ev.retrieved_by}</span>}
                  {ev.retrieval_score != null && <span>score {ev.retrieval_score.toFixed(3)}</span>}
                </div>
                <p className="evidence-text">{ev.text}</p>
              </div>
            ))}

            {missingIds.length > 0 && (
              <ErrorBanner>
                {found.length > 0
                  ? "Some cited evidence is no longer visible to you — access or status changed since this answer was generated."
                  : "Access or status changed; this source is no longer authorized to view."}
              </ErrorBanner>
            )}
          </>
        )}
      </div>
    </div>
  );
}
