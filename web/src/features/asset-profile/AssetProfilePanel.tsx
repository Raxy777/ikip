import { Panel, EmptyState } from "../../components/primitives";

export function AssetProfilePanel() {
  return (
    <Panel
      title="Asset profile"
      description="Asset-centric history and linked documents."
    >
      <EmptyState title="Not wired up yet">
        The plan calls for an asset profile — cited event history, linked documents, and
        actions per asset — once entity resolution and relationship storage exist (see the
        plan&rsquo;s conditional-release scope). <code>services/api</code> doesn&rsquo;t
        expose an asset-profile endpoint yet, so this screen has nothing real to call. Use{" "}
        <strong>Workspace</strong> with an asset ID filter (e.g. <code>P-101</code>) in the
        meantime — search and answer already scope by asset.
      </EmptyState>
    </Panel>
  );
}
