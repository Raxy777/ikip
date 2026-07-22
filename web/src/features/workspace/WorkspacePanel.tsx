import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useIdentity } from "../../lib/identity-context";
import type { Answer, Citation, EvidenceView, QueryRequest, SearchResponse } from "../../lib/types";
import { AuthorityBadge, StatementClassBadge, AbstentionReasonBadge } from "../../components/badges";
import { EmptyState, ErrorBanner, Panel } from "../../components/primitives";
import { EvidenceDrawer } from "../source-viewer/EvidenceDrawer";

type Mode = "answer" | "search";

export function WorkspacePanel() {
  const { identity } = useIdentity();

  const [mode, setMode] = useState<Mode>("answer");
  const [question, setQuestion] = useState("What failures has Pump P-101 experienced?");
  const [assetIdsInput, setAssetIdsInput] = useState("");
  const [sitesInput, setSitesInput] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [lastQuery, setLastQuery] = useState<QueryRequest | null>(null);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);

  const parseList = (raw: string) =>
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;

    const query: QueryRequest = {
      question: question.trim(),
      asset_ids: parseList(assetIdsInput),
      sites: parseList(sitesInput),
    };

    setLoading(true);
    setError(null);
    setAnswer(null);
    setSearchResult(null);
    setLastQuery(query);

    try {
      if (mode === "answer") {
        setAnswer(await api.answer(query, identity));
      } else {
        setSearchResult(await api.search(query, identity));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Panel
        title="Ask about authorized evidence"
        description="Every question is authorized before retrieval. Answers cite the exact authorized passages that support them, or abstain and say why."
      >
        <form className="query-form" onSubmit={submit}>
          <div className="mode-toggle" role="group" aria-label="Mode">
            <button type="button" aria-pressed={mode === "answer"} onClick={() => setMode("answer")}>
              Grounded answer
            </button>
            <button type="button" aria-pressed={mode === "search"} onClick={() => setMode("search")}>
              Evidence search only
            </button>
          </div>

          <div className="query-row">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What corrective action is recommended for Pump P-101?"
              rows={2}
              aria-label="Question"
            />
          </div>

          <div>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setShowFilters((s) => !s)}
              aria-expanded={showFilters}
              style={{ padding: "4px 0" }}
            >
              {showFilters ? "Hide" : "Narrow"} scope (asset / site filter) ⌄
            </button>
            {showFilters && (
              <div className="advanced-filters">
                <div className="field">
                  <label className="field-label" htmlFor="asset-ids">
                    Asset IDs
                  </label>
                  <input
                    id="asset-ids"
                    type="text"
                    placeholder="P-101, V-12"
                    value={assetIdsInput}
                    onChange={(e) => setAssetIdsInput(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="sites">
                    Sites
                  </label>
                  <input
                    id="sites"
                    type="text"
                    placeholder="site-a, site-b"
                    value={sitesInput}
                    onChange={(e) => setSitesInput(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button className="btn btn-primary" type="submit" disabled={loading || !question.trim()}>
              {loading ? "Asking…" : mode === "answer" ? "Get grounded answer" : "Search evidence"}
            </button>
            {loading && (
              <span className="status-line">
                <span className="spinner" /> Authorizing, retrieving, ranking…
              </span>
            )}
          </div>
        </form>
      </Panel>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      {mode === "answer" && answer && lastQuery && (
        <AnswerResults answer={answer} query={lastQuery} onOpenCitation={setOpenCitation} />
      )}

      {mode === "search" && searchResult && <SearchResults result={searchResult} />}

      {openCitation && lastQuery && (
        <EvidenceDrawer
          citation={openCitation}
          query={lastQuery}
          identity={identity}
          onClose={() => setOpenCitation(null)}
        />
      )}
    </div>
  );
}

function AnswerResults({
  answer,
  query,
  onOpenCitation,
}: {
  answer: Answer;
  query: QueryRequest;
  onOpenCitation: (c: Citation) => void;
}) {
  if (answer.outcome === "abstained" && answer.abstention) {
    const a = answer.abstention;
    return (
      <Panel title="Result">
        <div className="abstention-panel" data-reason={a.reason}>
          <div className="abstention-title">
            <AbstentionReasonBadge reason={a.reason} />
            <span>The system abstained</span>
          </div>
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.55 }}>{a.message}</p>
          {a.suggested_action && (
            <p style={{ margin: 0, fontSize: 12.5, color: "var(--text-muted)" }}>
              Suggested next step: {a.suggested_action}
            </p>
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      title="Grounded answer"
      description={`request ${answer.request_id} · config ${answer.config_version}`}
    >
      <div className="result-stack">
        {answer.conflicts && answer.conflicts.length > 0 && (
          <div className="conflict-panel">
            {answer.conflicts.length} conflicting source{answer.conflicts.length > 1 ? "s" : ""}{" "}
            disclosed rather than silently resolved.
            {answer.conflicts.map((c, i) => (
              <div key={i} style={{ marginTop: 6 }}>
                {c.description ?? JSON.stringify(c)}
              </div>
            ))}
          </div>
        )}

        {(answer.claims ?? []).map((claim) => (
          <div className="claim-card" key={claim.claim_id} data-class={claim.citation.statement_class}>
            <p className="claim-text">{claim.text}</p>
            <div className="claim-meta">
              <StatementClassBadge statementClass={claim.citation.statement_class} />
              {claim.citation.authority && <AuthorityBadge authority={claim.citation.authority} />}
              <span className="claim-id">{claim.claim_id}</span>
            </div>
            <div className="citation-links">
              {claim.citation.evidence_ids.map((id) => (
                <button
                  key={id}
                  className="citation-link"
                  onClick={() => onOpenCitation(claim.citation)}
                  title="Open cited source (re-checks authorization)"
                >
                  {id}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="panel-desc" style={{ marginTop: 16 }}>
        Scope: {query.sites?.length ? query.sites.join(", ") : "all authorized sites"}
        {query.asset_ids?.length ? ` · assets ${query.asset_ids.join(", ")}` : ""}
      </p>
    </Panel>
  );
}

function SearchResults({ result }: { result: SearchResponse }) {
  if (result.count === 0) {
    return (
      <Panel title="Authorized evidence">
        <EmptyState title="No authorized evidence matched">
          Nothing in scope for your current roles and sites matched this query. Restricted
          content, if any, is never revealed here or in the count.
        </EmptyState>
      </Panel>
    );
  }
  return (
    <Panel title="Authorized evidence" description={`${result.count} passage(s) — ranked, no model synthesis`}>
      <div className="result-stack">
        {result.evidence.map((ev: EvidenceView) => (
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
      </div>
    </Panel>
  );
}
