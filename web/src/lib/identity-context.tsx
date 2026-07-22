import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { DevIdentity } from "./types";

const STORAGE_KEY = "ikip.dev-identity";

const DEFAULT_IDENTITY: DevIdentity = {
  subject: "eng-a",
  roles: ["engineer"],
  sites: ["site-a"],
  verified: true,
};

function load(): DevIdentity {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_IDENTITY;
    const parsed = JSON.parse(raw);
    return {
      subject: parsed.subject ?? DEFAULT_IDENTITY.subject,
      roles: Array.isArray(parsed.roles) ? parsed.roles : DEFAULT_IDENTITY.roles,
      sites: Array.isArray(parsed.sites) ? parsed.sites : DEFAULT_IDENTITY.sites,
      verified: parsed.verified ?? true,
    };
  } catch {
    return DEFAULT_IDENTITY;
  }
}

interface IdentityContextValue {
  identity: DevIdentity;
  setIdentity: (next: DevIdentity) => void;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentityState] = useState<DevIdentity>(load);

  const setIdentity = (next: DevIdentity) => {
    setIdentityState(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const value = useMemo(() => ({ identity, setIdentity }), [identity]);

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): IdentityContextValue {
  const ctx = useContext(IdentityContext);
  if (!ctx) throw new Error("useIdentity must be used within an IdentityProvider");
  return ctx;
}

export const KNOWN_ROLES = ["engineer", "technician"] as const;
export const KNOWN_SITES = ["site-a", "site-b"] as const;
