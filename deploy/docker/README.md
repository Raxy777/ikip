# Container Images

One Dockerfile per deployable service. Each builds only its service plus the shared
packages it depends on, from the uv workspace.

Planned images:

- `api.Dockerfile` — Application API
- `retrieval.Dockerfile` — Retrieval & Answer Service
- `gateway.Dockerfile` — Model Gateway
- `ingestion.Dockerfile` — Ingestion Workers
- `web.Dockerfile` — Web Application (built static assets served behind ingress)

Images run as non-root with least privilege and carry no secrets; configuration is
injected at runtime (see `.env.example` for the key names).
