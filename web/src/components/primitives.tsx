import type { ReactNode } from "react";

export function Panel({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          {description && <p className="panel-desc">{description}</p>}
        </div>
        {actions}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-state-title">{title}</span>
      {children && <p className="panel-desc" style={{ margin: 0 }}>{children}</p>}
    </div>
  );
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div className="error-banner" role="alert">
      <span>⚠</span>
      <span>{children}</span>
    </div>
  );
}
