import { useState } from "react";
import { KNOWN_ROLES, KNOWN_SITES, useIdentity } from "../../lib/identity-context";

/**
 * There is no production identity provider wired up yet (identity.py refuses every request
 * unless IKIP_DEV_AUTH=1 is set on the server, and only then reads plain headers). This bar
 * is the honest UI for that: it lets you act as a given dev subject/roles/sites so you can
 * see authorization actually change what comes back, without pretending there's a login.
 */
export function IdentityBar() {
  const { identity, setIdentity } = useIdentity();
  const [open, setOpen] = useState(false);

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  return (
    <div className="identity-bar" style={{ position: "relative" }}>
      <button className="identity-summary" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span aria-hidden>◆</span>
        {identity.subject || "no subject"} · {identity.roles.join("+") || "no roles"} ·{" "}
        {identity.sites.join("+") || "no sites"}
      </button>

      {open && (
        <div className="panel identity-popover">
          <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field">
              <label className="field-label" htmlFor="dev-subject">
                Dev subject (X-Dev-Subject)
              </label>
              <input
                id="dev-subject"
                type="text"
                value={identity.subject}
                onChange={(e) => setIdentity({ ...identity, subject: e.target.value })}
              />
            </div>

            <div className="field">
              <span className="field-label">Roles (X-Dev-Roles)</span>
              <div className="chip-row">
                {KNOWN_ROLES.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className="chip"
                    aria-pressed={identity.roles.includes(role)}
                    onClick={() => setIdentity({ ...identity, roles: toggle(identity.roles, role) })}
                  >
                    {role}
                  </button>
                ))}
              </div>
              <span className="field-hint">No roles selected → scope denied → every answer abstains.</span>
            </div>

            <div className="field">
              <span className="field-label">Sites (X-Dev-Sites)</span>
              <div className="chip-row">
                {KNOWN_SITES.map((site) => (
                  <button
                    key={site}
                    type="button"
                    className="chip"
                    aria-pressed={identity.sites.includes(site)}
                    onClick={() => setIdentity({ ...identity, sites: toggle(identity.sites, site) })}
                  >
                    {site}
                  </button>
                ))}
              </div>
            </div>

            <div className="field">
              <span className="field-label">Token state (X-Dev-Verified)</span>
              <div className="chip-row">
                <button
                  type="button"
                  className="chip"
                  aria-pressed={identity.verified}
                  onClick={() => setIdentity({ ...identity, verified: true })}
                >
                  verified
                </button>
                <button
                  type="button"
                  className="chip"
                  aria-pressed={!identity.verified}
                  onClick={() => setIdentity({ ...identity, verified: false })}
                >
                  unverified
                </button>
              </div>
              <span className="field-hint">
                Unverified simulates a bad token — the pipeline must refuse rather than serve.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
