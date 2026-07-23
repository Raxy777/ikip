# Unified Asset & Operations Brain
### AI for Industrial Knowledge Intelligence — PS 8

**One line:** An evidence-grounded industrial brain that ingests every document type an asset-intensive plant owns — including CAD/engineering geometry — and answers operational questions with **claim-level citations, confidence, and a hard safety rule: cite or abstain, never guess.**

> Decision-support only. It never controls equipment and never authorizes maintenance, isolation, or safety action. That boundary is a design invariant, not a disclaimer.

---

## PAGE 1 — The Problem & Our Answer

### The problem, in the plant's own numbers *(PS 8)*
- **35%** of skilled hours lost searching, clarifying, or recreating documents that already exist. *(McKinsey 2024)*
- **7–12** disconnected document systems per large Indian plant — P&IDs, work orders, SOPs, inspection records, regulatory filings. *(NASSCOM-EY)*
- **18–22%** of unplanned downtime traced to that fragmentation — teams decide without full equipment history. *(BIS Research)*
- **25%** of India's experienced engineers retire within a decade, taking undocumented knowledge with them.

Fragmentation is not a filing problem. It is a **safety, quality, and efficiency** problem that compounds over time.

### Why existing tools fail here
| Enterprise search | Generic RAG chatbot | What industry actually needs |
|---|---|---|
| Keyword-only, no reasoning | Hallucinates confident answers | **Grounded** answers with citations |
| Blind to permissions | Leaks restricted content | **Authorize before retrieval** |
| Text only — ignores drawings & CAD | No engineering geometry | **Reads P&IDs, STEP, STL, assemblies** |
| No source of truth | No "I don't know" | **Safe abstention** on thin evidence |

### Our answer — the Unified Asset & Operations Brain
A single queryable intelligence layer over the whole heterogeneous corpus, built on four non-negotiable invariants:

1. **Authorize → then retrieve.** A restricted document can never enter ranking, prompts, citations, or logs. Authorization lives in *one* library every service imports — it is never re-implemented, never bypassed.
2. **Cite or abstain.** Every claim carries evidence IDs and a statement class. If evidence is insufficient or conflicting, the system abstains with a reason instead of fabricating — the trait a field technician can actually trust.
3. **Geometry is first-class knowledge.** 3D CAD is ingested, not skipped — STEP/STL/assembly formats today, plus a **shape-similarity search** that finds geometrically similar parts even across renamed or re-exported files. (P&ID / drawing digitization via computer vision is on the near-term roadmap.)
4. **Governance is fail-closed.** Export-controlled (ITAR/EAR) content, stale permissions, and un-sourced "loose files" all fail *closed* — excluded until proven safe, never leaked by default.

---

## PAGE 2 — How It Works (Technical Excellence & Innovation)

### End-to-end flow
```
                    UNTRUSTED DOCUMENTS                         USER QUESTION (mobile / desktop)
   PDFs · P&IDs · scans · spreadsheets · CAD (STEP/STL/         "Which assemblies use pump P-101,
   SolidWorks/CATIA/Creo) · email archives                       and what's its inspection interval?"
              │                                                            │
   ┌──────────▼──────────┐                                     ┌──────────▼───────────┐
   │  INGESTION PIPELINE  │                                     │  AUTHORIZE SCOPE      │ ← deny-by-default
   │  quarantine (magic-  │                                     │  (identity + roles +  │
   │  byte gate, sandbox) │                                     │   site + freshness)   │
   │  → tiered extract    │                                     └──────────┬───────────┘
   │  → chunk + enrich    │                                                │ (only if allowed)
   │  → resolve identity  │                          ┌─────────────────────▼─────────────────────┐
   │  → govern → index    │                          │   HYBRID RETRIEVAL (one authz filter)       │
   └──────────┬──────────┘                           │  LIVE: exact · lexical · SHAPE (3D geom)    │
              │                                       │  NEXT: semantic · relationship (ports ready)│
      ┌───────▼────────┐                              └─────────────────────┬─────────────────────┘
      │ GOVERNED STORE │◄─────── ACL sync ────────────►         MERGE + AUTHORIZE-FILTER + RANK
      │ knowledge graph│         (CMMS/EDMS/PLM)                (restricted dropped BEFORE ranking)
      │ + vectors +    │                                                    │
      │ shape vectors  │                                          ASSEMBLE MINIMUM EVIDENCE
      └────────────────┘                                                    │
                                                          SYNTHESIZE* → VALIDATE claims vs evidence
                                                          (*pilot: templated; model gateway = port)
                                                                            │
                                                        ┌───────────────────┴───────────────────┐
                                                    ANSWER with citations            ABSTAIN with reason
                                                    + confidence + links          (insufficient/conflict)
```

### The retrieval channels — why hybrid wins
All five channels share **one interface and one authorization filter**, so adding a channel never weakens the safety guarantee. Three are **live in the prototype today**; two are **implemented as ports with the wiring proven, activated next**.

- **Exact** *(live)* — asset tags & doc numbers (`P-101` matches `P-101`, never `P-1010`). Precision for identifiers.
- **Lexical / BM25** *(live)* — robust keyword recall.
- **SHAPE — our differentiator** *(live)* — a rotation/translation/scale-invariant **D2 geometric descriptor** computed from CAD meshes. Point to a reference part and retrieve *geometrically* similar parts — even when part numbers were changed or the file was re-exported. Ranked identically to text evidence and subject to the same authorization filter. (Invariance is unit-tested.)
- **Semantic** *(port ready, next)* — meaning-based match; the channel interface and merge/authorize path exist, the embedding adapter is the remaining wiring.
- **Relationship** *(port ready, next)* — asset-graph traversal (*"assemblies using part X"*, failure→cause). The BOM/assembly-edge data is already produced at ingestion (Phase 2); the query-side traversal channel is next.

> **Honest status:** the prototype answers with **3 live channels**; the architecture is built for **5**. The hard part — one authorization filter every channel obeys — is done, so the remaining two are adapters, not new safety surface.

### Tiered CAD ingestion — nothing gets silently dropped *(ADR-0004)*
| Tier | Formats | What we recover |
|---|---|---|
| **1 · Full geometry** | STEP, STL | Mesh, metrics, PMI, part cards, shape descriptor |
| **2 · Metadata** | SolidWorks, CATIA (OLE) | Properties, thumbnails, BOM/assembly edges, PN dedupe |
| **3 · Needs conversion** | Creo, NX | Convert → STEP → re-enter Tier 1 (FreeCAD subprocess seam, coded + tested with a stand-in; needs FreeCAD installed to run live) — else → review queue |
| **Blocked** | policy-restricted | Rejected with a recorded reason |

Every untrusted file is parsed inside a **sandbox** — any crash, timeout, or missing toolkit becomes a *routed outcome* (admit / review / reject), never a leak or a worker crash.

### Safety & governance engineering *(the hard part)*
- **Authorize-before-rank** enforced by *function signatures* — retrieval literally cannot run without a verified `AuthorizationContext`.
- **ACL freshness gate** — a stale permission cache fails closed **within its staleness bound**, so revoked access stops being served even if a sync webhook is missed.
- **PLM-governed vs loose files** — a part with no system-of-truth record is `authority=UNKNOWN` and excluded from ranking until reviewed.
- **Export control** — any ITAR/EAR/ECCN signal forces `classification=RESTRICTED`, overriding even a PLM-approved status. Fail-closed.
- **Claim validation** — the answer draft is treated as *untrusted* and every claim is checked against the authorized evidence before it can be returned; unsupported claims trigger abstention. *(In the pilot the draft comes from a deterministic templated gateway, not a live model — the validation and citation machinery is real; the model provider is a port, wired next.)*

### Architecture built to last
- **Contracts are single-source** — one citation/ACL/provenance schema, generated into every service, so definitions cannot drift.
- **Everything swappable behind ports** — vector store, model provider, queue, CAD converter are adapter changes, not rewrites (pgvector today, scale-trigger documented).
- **Evaluation is a release gate** — a runnable gate (`evaluation/run.py`) executes named correctness & security suites (grounding, abstention, ACL-leakage regressions) before a release ships. Expert-graded retrieval quality on a blind, access-controlled holdout is the documented production follow-up.

---

## PAGE 3 — Impact, Demo & Roadmap

### Business impact — mapped to the plant's pain
| Pain today | What the Brain changes | Value |
|---|---|---|
| 35% of hours spent searching | Grounded answer in seconds, with the source link | Skilled-hour recovery |
| 18–22% downtime from fragmentation | Cross-system context (history + OEM manual + inspections) in one answer | Fewer unplanned events |
| Knowledge cliff (retirements) | Undocumented know-how captured as cited, queryable evidence | Institutional memory preserved |
| Audit scramble | Traceable citations + append-only audit trail | Faster, defensible compliance |
| Wrong-answer risk | Cite-or-abstain + authorize-before-retrieval | **Trust — the adoption gate** |

### Live demo script
1. **Cited answer** — "Inspection interval for pump P-101?" → grounded, claim-level citation, link to the source (pilot answer is templated; the citation & validation path is real).
2. **Safe abstention** — a question with no supporting evidence → *"Insufficient evidence"* + reason, **not** a hallucination.
3. **Authorization** — the same query as a site-A vs site-B user → the restricted incident never appears for the unauthorized user (proven by the ACL-leakage test, not just claimed).
4. **Shape search** — a reference part's descriptor → geometrically similar parts ranked back; a rotated/rescaled copy scores near-identical (invariance is unit-tested).
5. **Governance fail-closed** — an ITAR-flagged part → classified `RESTRICTED` and withheld; a loose file with no PLM record → `UNKNOWN`, excluded from ranking until reviewed.

> *Next-milestone demo (architecture in place, activation pending):* relationship traversal — *"Which assemblies use part X?"* — using the assembly-edge/BOM data already produced at ingestion.

### Evaluation focus *(directly per PS 8)*
Entity-extraction accuracy across document types · answer quality on domain-expert questions · knowledge-graph linkage completeness · time-to-answer vs traditional search · compliance-gap detection · cross-functional discovery — all measured by the built-in evaluation gate.

### Why we win on the judging criteria
| Criterion | Weight | Our edge |
|---|---|---|
| **Innovation** | 25% | Shape-similarity retrieval over CAD geometry; authorize-before-rank as an enforced invariant; cite-or-abstain |
| **Business Impact** | 25% | Directly attacks the 35% / 18–22% / knowledge-cliff numbers; trust-first = adoptable |
| **Technical Excellence** | 20% | Single-source contracts, ports/adapters, sandboxed tiered ingestion, evaluation-gated releases |
| **Scalability** | 15% | Stateless services, pgvector-behind-a-port with a documented scale trigger, queue-driven ingestion |
| **User Experience** | 15% | Cited Q&A + source viewer designed for field techs; abstention that builds trust (web client is an early pilot) |

### Roadmap
- **Now (prototype):** authorization + fail-closed governance, tiered CAD ingest (Phases 1–4) with sandboxed extraction, **3 live retrieval channels (exact · lexical · shape)** on a 5-channel authorization-uniform architecture, cite-or-abstain with real claim validation, runnable pilot API + evaluation gate.
- **Next:** activate semantic + relationship channels (ports ready), wire the real model gateway (replacing the templated pilot), production OIDC/SAML, live CMMS/EDMS/PLM ACL sync, P&ID computer-vision symbol extraction.
- **Later:** predictive-maintenance RCA agent, proactive "lessons-learned" push (warn teams before conditions recur), multi-plant federation.

---

**Deliverables:** Working prototype ✓ · Architecture diagrams (7 C4/trust-boundary/sequence, `docs/architecture/`) ✓ · This deck · Demo video.

*The organizations that solve knowledge fragmentation first gain a structural advantage in how they operate, maintain, and improve their assets. This is that solution — built trust-first.*
