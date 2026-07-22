import { useState } from "react";
import { IdentityBar } from "./features/identity-bar/IdentityBar";
import { WorkspacePanel } from "./features/workspace/WorkspacePanel";
import { AdminPanel } from "./features/admin/AdminPanel";
import { AssetProfilePanel } from "./features/asset-profile/AssetProfilePanel";
import { UploadPanel } from "./features/uploads/UploadPanel";
import { ReviewQueuePanel } from "./features/review-queue/ReviewQueuePanel";

type Tab = "uploads" | "workspace" | "asset-profile" | "review-queue" | "admin";

const TABS: { id: Tab; label: string }[] = [
  { id: "uploads", label: "Uploads" },
  { id: "workspace", label: "Workspace" },
  { id: "asset-profile", label: "Asset profile" },
  { id: "review-queue", label: "Review queue" },
  { id: "admin", label: "Admin" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("workspace");

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M6 17V9l6-4 6 4v8" stroke="#4FA3D1" strokeWidth="1.6" strokeLinejoin="round" />
              <path d="M9.5 17v-5h5v5" stroke="#E0A430" strokeWidth="1.6" />
            </svg>
          </div>
          <div>
            <div className="brand-name">Industrial Knowledge Intelligence</div>
            <div className="brand-sub">Decision support — never controls equipment</div>
          </div>
        </div>

        <nav className="nav-tabs" role="tablist" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              className="nav-tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <IdentityBar />
      </header>

      <main className="app-main">
        {tab === "uploads" && <UploadPanel />}
        {tab === "workspace" && <WorkspacePanel />}
        {tab === "asset-profile" && <AssetProfilePanel />}
        {tab === "review-queue" && <ReviewQueuePanel />}
        {tab === "admin" && <AdminPanel />}
      </main>

      <footer className="app-footer">
        dev identity via X-Dev-* headers · IKIP_DEV_AUTH must be 1 on the API · not for production auth
      </footer>
    </div>
  );
}
