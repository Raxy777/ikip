# Web Application

Browser UI: governed search, cited Q&A, source viewer with highlighted citations, asset
profiles, upload, human review queue, and administration.

## Feature areas (`src/features/`)

| Feature | Purpose |
|---|---|
| `search` | Governed search with asset/site filters |
| `answer` | Cited answer view — claim-level citations, statement-class + authority indicators, disclosed conflicts, or abstention |
| `source-viewer` | Highlighted source preview; re-checks authorization on open |
| `asset-profile` | Asset-centric history and linked documents |
| `review-queue` | Reviewer actions: authority, identity, ambiguity, merge/split |
| `admin` | Document governance, ACLs, corrections, audit |

## Generated types

`src/lib/generated/` holds TypeScript types generated from `contracts/schemas` via
`npm run codegen`. Do not hand-edit; the directory is git-ignored except its marker.
