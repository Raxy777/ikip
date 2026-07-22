import { Panel, EmptyState } from "../../components/primitives";

export function ReviewQueuePanel() {
  return (
    <Panel
      title="Review queue"
      description="Reviewer actions: authority, identity, ambiguity, merge/split."
    >
      <EmptyState title="Not wired up yet">
        <code>contracts/openapi/api.v1.yaml</code> documents <code>POST /feedback</code> for
        submitting corrections that create governed review items, but that route isn&rsquo;t
        implemented in <code>services/api</code> yet — only <code>/search</code>,{" "}
        <code>/answer</code>, and <code>/admin/acl/revoke</code> are. Once feedback and
        governance review endpoints exist, this screen is the right place to wire them in —
        it&rsquo;s built to the same layout as Workspace and Admin so that&rsquo;s a small
        addition, not a new screen.
      </EmptyState>
    </Panel>
  );
}
