# Upload pipeline demo (prototype)

This vertical slice is a local decision-support prototype, not a production security or CAD claim.

```sh
docker compose -f deploy/compose/docker-compose.yml up --build
# UI: http://localhost:8080 ; MinIO console: http://localhost:9001
```

The API migrates PostgreSQL on start, stores originals in MinIO, and persists states, chunks and
shapes in PostgreSQL. Compose deliberately enables insecure `X-Dev-*` identity; do not expose it.
Choose **Uploads**, upload PDF/STL/STEP, watch state, preview STL, then search distinctive extracted
text in **Workspace**. Stock Compose gracefully retains/indexes STEP metadata when optional OCCT is
absent. Existing no-infrastructure development remains `IKIP_STORAGE_PROFILE=memory`.

```sh
curl -F file=@manual.pdf -H 'X-Dev-Subject: eng-a' -H 'X-Dev-Roles: engineer' \
 -H 'X-Dev-Sites: site-a' http://localhost:8080/api/documents
```
