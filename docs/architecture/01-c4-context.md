# C4 Context Diagram

**System:** Industrial Knowledge Intelligence Platform — Unified Asset & Operations Brain  
**Scope:** System landscape and external actors; decision support only, with no equipment-control path.

```mermaid
graph LR
maint["👤 Maintenance Engineer<br/><br/>Reviews asset history, work orders, and supporting records"]
ops["👤 Operations Technician<br/><br/>Finds the applicable approved procedure"]
rel["👤 Reliability Engineer<br/><br/>Identifies recurring failure evidence across documents"]
qa["👤 Quality / Compliance Lead<br/><br/>Locates requirements and objective evidence"]
owner["👤 Information Owner / Admin<br/><br/>Governs documents, authority, access policy, and corrections"]
ikip["🏢 Industrial Knowledge Intelligence Platform<br/><br/><b>Unified Asset & Operations Brain</b><br/>Ingests governed documents.<br/>Links assets to events and requirements.<br/>Answers questions with claim-level citations.<br/>Safely abstains when evidence is insufficient.<br/><br/><b>Decision-support only — never controls equipment.</b>"]
idp["☁️ Identity Provider (SSO)<br/><br/>Authenticates users and supplies roles for document-level authorization"]
sor["☁️ Asset System of Record<br/><br/>Owns canonical asset IDs used for entity resolution (e.g., CMMS asset registry)"]
src["☁️ Document Source Systems<br/><br/>CMMS / EDMS / QMS<br/>Origin of manuals, work orders, inspection reports, procedures.<br/>Read-only in the core release."]
llm["☁️ Approved Model Provider<br/><br/>Hosted or local LLM behind a gateway.<br/>Structured extraction and evidence-only answer synthesis.<br/>No retention or training on customer data."]
maint -->|"HTTPS<br/>Asks cited asset questions,<br/>views timelines"| ikip
ops -->|"HTTPS<br/>Searches governed procedures,<br/>opens source viewer"| ikip
rel -->|"HTTPS<br/>Runs cross-document synthesis queries"| ikip
qa -->|"HTTPS<br/>Looks up requirements<br/>and evidence links"| ikip
owner -->|"HTTPS<br/>Uploads, governs,<br/>reviews, corrects, audits"| ikip
ikip -->|"OIDC / SAML<br/>Delegates authentication,<br/>maps roles"| idp
ikip -->|"Read-only API / export<br/>Validates canonical asset identity"| sor
src -->|"Upload / controlled export<br/>Provides documents for controlled ingestion"| ikip
ikip -->|"TLS<br/>Sends authorized evidence only;<br/>receives grounded output"| llm
```