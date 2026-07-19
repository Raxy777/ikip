# Sequence Diagram — Query Flow

**System:** Industrial Knowledge Intelligence Platform — Unified Asset & Operations Brain  
**Scenario:** An authorized user asks an asset or operations question and receives a grounded, claim-cited answer—or a safe abstention.

```mermaid
sequenceDiagram
    autonumber
    actor User as Authorized User
    participant Web as Web Application
    participant IdP as Identity Provider
    participant API as Application API
    participant DB as Governed Knowledge Store
    participant RAG as Retrieval & Answer Service
    participant GW as Model Gateway
    participant LLM as Approved Model Provider
    participant Obj as Object Storage
    participant Obs as Audit & Evaluation

    User->>Web: Enter question and optional asset/site filters
    Web->>IdP: Authenticate or refresh session
    IdP-->>Web: Signed identity and role claims
    Web->>API: Submit query with token and filters
    API->>API: Validate token, map roles, rate-limit, create request ID
    API->>DB: Load user scope, document ACL policy, and canonical asset context
    DB-->>API: Authorized sites, roles, policy, and asset identity

    alt Identity invalid or query not permitted
        API-->>Web: Deny request without revealing restricted content
        API-->>Obs: Record denied authorization event
        Web-->>User: Access denied or reauthentication required
    else Request is permitted
        API->>RAG: Query plus verified authorization and applicability context
        RAG->>DB: Exact-ID and lexical search with ACL, site, status, authority, revision, and applicability filters
        DB-->>RAG: Authorized lexical candidates only
        RAG->>DB: Semantic/vector and relationship search using the same filters
        DB-->>RAG: Authorized semantic and relationship candidates only
        RAG->>RAG: Merge, deduplicate, rerank, diversify, and check authority

        alt No adequate authorized evidence
            RAG-->>API: Abstention with reason category and safe next step
            API-->>Obs: Record retrieval set, policy result, and abstention
            API-->>Web: Insufficient, ambiguous, stale, conflicting, or unavailable evidence
            Web-->>User: Show abstention and suggested source/owner action
        else Adequate evidence exists
            RAG->>RAG: Assemble minimum authorized evidence with source coordinates
            RAG->>GW: Evidence-only prompt, statement rules, citation schema, and evidence
            GW->>GW: Enforce provider, residency, retention, token, and content policy
            GW->>LLM: Send minimum authorized evidence over TLS
            LLM-->>GW: Structured draft answer with evidence references
            GW->>GW: Treat output as untrusted; validate schema and policy
            GW-->>RAG: Validated draft or validation failure
            RAG->>RAG: Verify claim support, citation coverage, conflicts, and statement labels

            alt Output invalid or claims unsupported
                RAG-->>API: Safe abstention or evidence-only search results
                API-->>Obs: Record validation failure and abstention
                API-->>Web: Answer unavailable; show authorized evidence list
                Web-->>User: Display safe fallback
            else Output passes validation
                RAG-->>API: Grounded answer, claim-level citations, authority indicators, and conflicts
                API-->>Obs: Record request, evidence IDs, versions, citations, policy result, and latency
                API-->>Web: Return answer and citation metadata
                Web-->>User: Display answer with source links and warnings

                opt User opens a citation
                    Web->>API: Request cited page/section
                    API->>DB: Recheck current document authorization and version
                    DB-->>API: Access decision and artifact reference
                    alt Citation remains authorized
                        API->>Obj: Request short-lived preview for exact source location
                        Obj-->>API: Authorized preview
                        API-->>Web: Highlighted source page or section
                        Web-->>User: Show supporting evidence
                    else Access changed or source withdrawn
                        API-->>Web: Citation preview unavailable
                        API-->>Obs: Record denied preview attempt
                        Web-->>User: Explain access or status change without leakage
                    end
                end

                opt User submits feedback or correction
                    User->>Web: Rate answer or report an issue
                    Web->>API: Submit feedback with answer/request ID
                    API->>DB: Store feedback or create governed review item
                    API-->>Obs: Record feedback and review event
                end
            end
        end
    end
```

## Query-flow invariants

1. Authentication and document-level authorization occur before retrieval.
2. Exact, lexical, semantic, and relationship searches use the same ACL and applicability constraints.
3. Only the minimum authorized evidence reaches the model gateway and provider.
4. Retrieved document text is treated as data, never as executable instruction.
5. Model output is untrusted until schema, citation, support, conflict, and statement-class checks pass.
6. Missing, ambiguous, conflicting, stale, or unauthorized evidence causes disclosure or abstention—not invention.
7. Citation access is checked again when the user opens the source because permissions and status can change.
8. The audit record uses governed identifiers and redaction rules; unnecessary document content and secrets are not logged.
