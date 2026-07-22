import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useIdentity } from "../../lib/identity-context";
import { Panel } from "../../components/primitives";

const SEED_DOCUMENTS = [
  { id: "pump-manual", site: "site-a", roles: "engineer, technician" },
  { id: "valve-procedure", site: "site-a", roles: "engineer" },
  { id: "restricted-incident", site: "site-b", roles: "engineer" },
];

export function AdminPanel() {
  const { identity } = useIdentity();
  const [health, setHealth] = useState<"checking" | "up" | "down">("checking");
  const [documentId, setDocumentId] = useState("pump-manual");
  const [revoking, setRevoking] = useState(false);
  const [result, setResult] = useState<{ document_id: string; revoked: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .healthz()
      .then(() => setHealth("up"))
      .catch(() => setHealth("down"));
  }, []);

  async function revoke() {
    setRevoking(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.revokeAcl({ document_id: documentId.trim() }, identity);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Revoke failed.");
    } finally {
      setRevoking(false);
    }
  }

  return (
    <div className="admin-grid">
      <Panel title="API status" description="GET /healthz">
        <div className="status-line">
          <span
            className="badge-dot"
            style={{
              background: health === "up" ? "var(--green)" : health === "down" ? "var(--red)" : "var(--text-faint)",
            }}
          />
          {health === "checking" && "Checking…"}
          {health === "up" && "API reachable"}
          {health === "down" && "API unreachable — is uvicorn running with IKIP_DEV_AUTH=1?"}
        </div>

        <h4 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-faint)", marginTop: 20 }}>
          Current dev identity
        </h4>
        <div className="kv-row">
          <span className="kv-key">subject</span>
          <span>{identity.subject}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">roles</span>
          <span>{identity.roles.join(", ") || "—"}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">sites</span>
          <span>{identity.sites.join(", ") || "—"}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">verified</span>
          <span>{String(identity.verified)}</span>
        </div>
      </Panel>

      <Panel
        title="Revoke a document's ACL"
        description="POST /admin/acl/revoke — takes effect immediately, no reindexing. The seeded dev corpus below is defined in services/api/src/ikip_api/services.py."
      >
        <div className="field">
          <label className="field-label" htmlFor="doc-id">
            Document ID
          </label>
          <input id="doc-id" type="text" value={documentId} onChange={(e) => setDocumentId(e.target.value)} />
        </div>

        <div className="seed-doc-list">
          {SEED_DOCUMENTS.map((d) => (
            <div className="seed-doc" key={d.id}>
              <button className="btn btn-ghost" style={{ padding: 0, fontFamily: "inherit" }} onClick={() => setDocumentId(d.id)}>
                {d.id}
              </button>
              <span style={{ color: "var(--text-faint)" }}>
                {d.site} · {d.roles}
              </span>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 14 }}>
          <button className="btn btn-danger" onClick={revoke} disabled={revoking || !documentId.trim()}>
            {revoking ? "Revoking…" : "Revoke ACL"}
          </button>
        </div>

        {error && (
          <p style={{ color: "var(--red)", fontSize: 12.5, marginTop: 10 }}>{error}</p>
        )}
        {result && (
          <p style={{ fontSize: 12.5, marginTop: 10, color: result.revoked ? "var(--green)" : "var(--text-muted)" }}>
            {result.document_id}: {result.revoked ? "revoked ✓ — try answering about it again" : "not revoked"}
          </p>
        )}
      </Panel>
    </div>
  );
}
