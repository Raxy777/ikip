# Web Application

<<<<<<< HEAD
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
=======
Browser UI for the API in `services/api` (`ikip_api.app:app`): governed search, cited
answers with claim-level citations, a source viewer that re-checks authorization, and an
admin panel for live ACL revocation. No backend code was changed to build this — the dev
server proxies API requests instead (see "Connecting to the API" below).

## Running it

```bash
# Terminal 1 — the API (from repo root)
cd services/api
IKIP_DEV_AUTH=1 uv run uvicorn ikip_api.app:app --app-dir src --reload

# Terminal 2 — the web app
cd web
npm install
npm run dev
```

Open http://localhost:5173. Set a dev subject/roles/sites in the identity bar (top right) —
without at least one role, every answer abstains, since the dev API fails closed with no
scope. `eng-a` / `engineer` / `site-a` is the default and matches the seeded demo corpus in
`services/api/src/ikip_api/services.py`.

## What's actually implemented vs. what's still a stub

`services/api` currently implements four endpoints:

| Method & path | Wired up in |
|---|---|
| `GET /healthz` | Admin panel |
| `POST /search` | Workspace (evidence-search mode) |
| `POST /answer` | Workspace (grounded-answer mode), source viewer's re-check |
| `POST /admin/acl/revoke` | Admin panel |

`services/api/src/ikip_api/services.py` now also wires up a `SHAPE` retrieval channel
(CAD part geometric-similarity search, `services/retrieval/.../pipeline/search_shape.py`).
It's included in `types.ts`'s `RetrievalChannel` union and rendered wherever
`retrieved_by` is shown, but `QueryRequest` (`schemas.py`) has no `shape_descriptor` field
yet, so the channel is a no-op through this HTTP API today — it always returns `[]` until a
request field for the reference descriptor is added server-side.

`contracts/openapi/api.v1.yaml` documents a larger production surface —
`/api/v1/query`, `GET /citations/{claimId}/source`, `POST /feedback`, bearer-JWT auth — that
matches the target architecture in `ARCHITECTURE.md` but isn't implemented in `services/api`
yet (only `services/gateway/src/ikip_gateway/prompt_isolation.py` exists there, with no HTTP
surface). The **Asset profile** and **Review queue** screens say so plainly instead of
faking data against endpoints that don't exist. The source viewer approximates
`GET /citations/{claimId}/source`'s "re-checks authorization on open" behavior by re-running
the same `/search` query against live ACL state, since that's the real guarantee the actual
`/search` endpoint already provides.

## Feature areas (`src/features/`)

| Feature | Purpose | Backed by |
|---|---|---|
| `workspace` | Governed search and cited answers — claim-level citations, statement-class + authority badges, disclosed conflicts, or abstention | `/search`, `/answer` |
| `source-viewer` | Evidence drawer opened from a citation; re-checks authorization | `/search` |
| `admin` | API health, dev identity summary, ACL revoke demo | `/healthz`, `/admin/acl/revoke` |
| `identity-bar` | Sets the `X-Dev-Subject` / `X-Dev-Roles` / `X-Dev-Sites` / `X-Dev-Verified` headers the dev auth stub reads (`ikip_api/identity.py`) | — (client-only; not real auth) |
| `asset-profile` | Placeholder — no asset-profile endpoint exists yet | — |
| `review-queue` | Placeholder — no feedback/review endpoint exists yet | — |

## Connecting to the API

`services/api` has no CORS middleware, and none was added — that's a backend change and out
of scope here. Instead:

- **Dev (`npm run dev`)**: `vite.config.ts` proxies `/api/*` to `VITE_API_PROXY_TARGET`
  (default `http://localhost:8000`), stripping the `/api` prefix. The browser only ever
  talks to the Vite origin, so CORS never comes up.
- **Production build (`npm run build`)**: there is no dev proxy. Either put a same-origin
  reverse proxy (e.g. nginx) in front of both, or set `VITE_API_BASE_URL` to the API's
  origin and add `fastapi.middleware.cors.CORSMiddleware` to `services/api/src/ikip_api/app.py`
  — a small, explicit backend change, not one this frontend-only pass makes silently.

See `.env.example` for both variables.

## Types (`src/lib/types.ts`)

Hand-written TypeScript mirrors of `contracts/schemas/*` and
`services/api/src/ikip_api/schemas.py`, kept in lock-step by field name and enum value — the
same approach `ikip_contracts.models` takes on the Python side until codegen exists.

`src/lib/generated/` is reserved for `npm run codegen` output once
`contracts/codegen/generate.py` / the `json-schema-to-typescript` step is wired up for the
web package; it's currently empty (git-ignored except its `.gitkeep` marker) and unused by
the app.
>>>>>>> e58cf65 (Frontend)
