import type { AbstentionReason, Authority, StatementClass } from "../lib/types";

const AUTHORITY_LABEL: Record<Authority, string> = {
  approved: "Approved",
  draft: "Draft",
  superseded: "Superseded",
  withdrawn: "Withdrawn",
  unknown: "Unknown authority",
};

export function AuthorityBadge({ authority }: { authority: Authority }) {
  return (
    <span className={`badge badge-${authority}`} title={authorityTitle(authority)}>
      <span className="badge-dot" />
      {AUTHORITY_LABEL[authority]}
    </span>
  );
}

function authorityTitle(authority: Authority): string {
  switch (authority) {
    case "approved":
      return "Current, approved guidance.";
    case "draft":
      return "Not yet approved. May inform current guidance but is not final.";
    case "superseded":
      return "Replaced by a newer revision. Historical context only.";
    case "withdrawn":
      return "Withdrawn. Must not be treated as guidance.";
    default:
      return "Authority state could not be established. Discovery/history use only — not an approved instruction.";
  }
}

const STATEMENT_CLASS_LABEL: Record<StatementClass, string> = {
  historical_observation: "Historical observation",
  recommendation: "Recommendation",
  approved_procedure: "Approved procedure",
  completed_work: "Completed work",
  inference: "Inference",
};

const STATEMENT_CLASS_TITLE: Record<StatementClass, string> = {
  historical_observation: "A record of something observed. Not an instruction.",
  recommendation: "A suggested action. Not yet an approved procedure or a completion record.",
  approved_procedure: "A governed, approved procedure.",
  completed_work: "A record that work was actually completed — not inferred from a recommendation.",
  inference: "Derived by the system from evidence, not stated directly by a source.",
};

export function StatementClassBadge({ statementClass }: { statementClass: StatementClass }) {
  return (
    <span className={`badge badge-${statementClass}`} title={STATEMENT_CLASS_TITLE[statementClass]}>
      <span className="badge-dot" />
      {STATEMENT_CLASS_LABEL[statementClass]}
    </span>
  );
}

const ABSTENTION_LABEL: Record<AbstentionReason, string> = {
  insufficient: "Insufficient evidence",
  ambiguous: "Ambiguous",
  stale: "Evidence stale",
  conflicting: "Conflicting sources",
  unauthorized_scope: "Outside authorized scope",
  unavailable: "Temporarily unavailable",
};

export function AbstentionReasonBadge({ reason }: { reason: AbstentionReason }) {
  const tone =
    reason === "unauthorized_scope" || reason === "conflicting"
      ? "badge-withdrawn"
      : reason === "unavailable"
        ? "badge-superseded"
        : "badge-draft";
  return (
    <span className={`badge ${tone}`}>
      <span className="badge-dot" />
      {ABSTENTION_LABEL[reason]}
    </span>
  );
}
