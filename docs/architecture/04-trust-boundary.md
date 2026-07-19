# Trust Boundary Diagram

**System:** Industrial Knowledge Intelligence Platform — Unified Asset & Operations Brain  
**View:** Logical security and data-trust boundaries. Every imported document is treated as untrusted content, even when it arrives from an approved source system.

```mermaid
graph LR
    subgraph UZ["TB-0 — Untrusted User and Content Zone"]
        browser["Managed or unmanaged browser<br/>user input and query text"]
        source["Document Source Systems / Uploads<br/>CMMS · EDMS · QMS<br/><b>content is never trusted as instruction</b>"]
    end

    subgraph EX["TB-1 — Enterprise Services — Externally Managed Trust"]
        idp["Identity Provider<br/>signed identity and role assertions"]
        asset["Asset System of Record<br/>canonical asset IDs<br/>read-only integration"]
    end

    subgraph PLATFORM["Controlled Production Security Boundary"]
        direction LR

        subgraph EDGE["TB-2 — Edge / Request Boundary"]
            ingress["TLS Ingress and WAF<br/>request limits · filtering · threat detection"]
        end

        subgraph APP["TB-3 — Private Application Boundary"]
            web["Web Application<br/>session and UI controls"]
            api["Application API<br/>token validation · role mapping<br/>object-level authorization · audit"]
            retrieval["Retrieval and Answer Service<br/>ACL + applicability filter first<br/>citation · conflict · abstention policy"]
            gateway["Model Gateway<br/>approved models only<br/>prompt isolation · egress policy<br/>input/output validation"]
        end

        subgraph INGEST["TB-4 — Content Quarantine and Processing Boundary"]
            quarantine["Upload Quarantine<br/>type/size/checksum validation<br/>malware and duplicate screening"]
            workers["Sandboxed Ingestion Workers<br/>parse · OCR · structure extraction<br/>quality checks · bounded enrichment"]
            review["Human Review Queue<br/>authority · identity · ambiguity<br/>high-impact merge/split approval"]
        end

        subgraph DATA["TB-5 — Restricted Governed Data Boundary"]
            pg[("Governed PostgreSQL<br/>ACLs · metadata · chunks · vectors<br/>entities · provenance · audit state")]
            objects[("Encrypted Object Storage<br/>originals · previews · extraction artifacts<br/>versioned and checksummed")]
            backup[("Protected Backup Vault<br/>isolated access · retention controls<br/>tested restore")]
        end

        subgraph OPS["TB-6 — Privileged Operations Boundary"]
            admin["Restricted Administrator Access<br/>strong authentication · least privilege<br/>approved change and recovery actions"]
            secrets["Managed Identities, Secrets and Keys<br/>rotation · scoped service access"]
            telemetry["Security and Audit Telemetry<br/>redaction · append-only audit trail<br/>alerts and evaluation evidence"]
        end
    end

    subgraph MODEL["TB-7 — Approved Model-Processing Boundary"]
        llm["Approved Hosted or Local Model<br/>no customer-data training<br/>approved retention and residency"]
    end

    browser -->|"1 · HTTPS · CSRF/session controls<br/>rate and input limits"| ingress
    ingress -->|"2 · sanitized request"| web
    web -->|"3 · authenticated API call"| api
    web -->|"OIDC / SAML authentication"| idp
    api -->|"4 · verify signature, issuer, audience,<br/>expiry and mapped roles"| idp

    source -->|"5 · controlled upload / export<br/>assume malicious content"| ingress
    ingress -->|"6 · isolated registration"| quarantine
    quarantine -->|"7 · release only after validation<br/>and malware screening"| workers
    workers -->|"8 · ambiguous or low-quality results"| review
    review -->|"9 · signed reviewer decision"| workers
    workers -->|"10 · read-only identity validation<br/>response schema and site checks"| asset

    api -->|"11 · per-request identity context<br/>deny by default"| retrieval
    retrieval -->|"12 · ACL, site, applicability,<br/>authority and revision filters"| pg
    api -->|"13 · authorized metadata operations<br/>scoped service identity"| pg
    api -->|"14 · short-lived authorized preview access"| objects
    workers -->|"15 · governed writes with lineage<br/>idempotency and extraction versions"| pg
    workers -->|"16 · immutable original and<br/>versioned derived artifacts"| objects

    retrieval -->|"17 · minimum authorized evidence only<br/>document text isolated from instructions"| gateway
    workers -->|"18 · bounded structured extraction request"| gateway
    gateway -->|"19 · outbound TLS · allow-listed route<br/>data minimization"| llm
    llm -->|"20 · untrusted model output<br/>schema, citation and policy validation"| gateway

    pg -->|"21 · encrypted policy-controlled backup"| backup
    objects -->|"22 · encrypted policy-controlled backup"| backup

    admin -->|"23 · privileged approved operations"| api
    admin -->|"24 · restricted restore access"| backup
    secrets -.->|"scoped runtime identity and keys"| ingress
    secrets -.->|"scoped runtime identity and keys"| api
    secrets -.->|"scoped runtime identity and keys"| retrieval
    secrets -.->|"scoped runtime identity and keys"| workers
    secrets -.->|"scoped runtime identity and keys"| gateway

    ingress -.->|"25 · threat events"| telemetry
    api -.->|"26 · authorization and audit events<br/>no unnecessary document content"| telemetry
    retrieval -.->|"27 · evidence IDs, decisions and quality<br/>policy-controlled query/answer logging"| telemetry
    workers -.->|"28 · lineage, quality and failures"| telemetry
    gateway -.->|"29 · policy, usage and provider health<br/>secrets and payloads redacted"| telemetry

    classDef untrusted fill:#fee2e2,stroke:#b91c1c,color:#111;
    classDef external fill:#fef3c7,stroke:#b45309,color:#111;
    classDef edge fill:#ffedd5,stroke:#c2410c,color:#111;
    classDef app fill:#dbeafe,stroke:#1d4ed8,color:#111;
    classDef ingest fill:#fae8ff,stroke:#a21caf,color:#111;
    classDef data fill:#dcfce7,stroke:#15803d,color:#111;
    classDef ops fill:#ede9fe,stroke:#6d28d9,color:#111;
    classDef model fill:#fce7f3,stroke:#be185d,color:#111;

    class browser,source untrusted;
    class idp,asset external;
    class ingress edge;
    class web,api,retrieval,gateway app;
    class quarantine,workers,review ingest;
    class pg,objects,backup data;
    class admin,secrets,telemetry ops;
    class llm model;
```

## Boundary rules

| Boundary | Trust change | Mandatory controls |
|---|---|---|
| TB-0 → TB-2 | Untrusted client request or imported content enters the platform | TLS, WAF, request/type/size limits, rate controls, upload isolation, audit event |
| TB-1 ↔ TB-3/TB-4 | Externally managed identity and asset claims influence decisions | Signed-token verification, issuer/audience/expiry checks, controlled role mapping, read-only asset access, response validation |
| TB-2 → TB-3 | Edge-filtered traffic reaches private services | Private routing, authenticated requests, session/CSRF protection, least-privilege service identity |
| TB-2 → TB-4 | Imported content enters processing | Quarantine, checksum, duplicate and malware checks, parser isolation, hidden/adversarial-content handling |
| TB-3 ↔ TB-5 | Application reads or changes governed data | Deny-by-default document authorization, object-level ACLs, private endpoints, encryption, lineage and audit logging |
| TB-4 → TB-5 | Machine-extracted content becomes governed data | Structured schema, evidence coordinates, confidence/quality state, idempotency, versioning, human review for ambiguity |
| TB-3 → TB-7 | Authorized evidence leaves for model processing | Gateway-only egress, minimum evidence, instruction/content separation, approved provider/residency/retention, no training |
| TB-7 → TB-3 | Model output returns to the trusted application | Treat as untrusted, validate schema and citations, enforce statement labels/conflict disclosure/abstention; never execute output |
| TB-6 → all production zones | Privileged operational action crosses into runtime or data | Strong authentication, least privilege, approval and separation of duties, complete audit trail, scoped secrets |
| TB-5 → backup | Governed data enters longer-lived recovery storage | Encryption, access isolation, retention/deletion rules, restore testing and deletion verification |

## Non-negotiable security invariants

1. **Authorize before retrieval:** restricted text must not enter ranking, prompts, citations, previews, summaries, logs, or inference-visible context.
2. **Treat documents as data, never instructions:** embedded prompts, hidden text, links, or adversarial passages cannot override platform policy.
3. **Treat model output as untrusted:** only validated, evidence-supported claims may be shown; otherwise disclose conflict or abstain.
4. **Preserve provenance:** originals are not overwritten; every derivative records its source coordinates and processing versions.
5. **Separate privileges:** end users, reviewers, ingestion workers, application services, model gateway, and administrators receive distinct scoped identities.
6. **Minimize disclosure:** only necessary authorized evidence crosses the model boundary; telemetry and errors redact secrets and sensitive content.
7. **Make corrections and deletion complete:** changes propagate to facts, links, embeddings, indexes, caches, previews, histories, and backups according to approved policy.

## Decisions required before implementation

- Define network segmentation, private endpoints, egress allow-list, and whether the approved model runs inside or outside the customer-controlled environment.
- Define role-to-document policy, site scoping, reviewer privileges, emergency access, session lifetime, and administrator approval workflow.
- Select malware, file-sanitization, parser-sandbox, secrets, key-management, DLP, and security-monitoring controls.
- Approve model-provider residency, retention, training, incident-notification, and subprocessor terms.
- Define which query, evidence, answer, and audit fields may be logged and their retention/deletion periods.
