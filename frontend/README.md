# Web UI

This Vite + React + TypeScript client is the platform's primary web interface (Phase 3).
It covers the dashboard, device inventory and detail, the LLDP-evidence topology map,
backups, backup schedules, configuration history with deterministic diffs, and the event
log. Alerts, the AI assistant and settings are explicit placeholders for later phases.

Start the FastAPI server on port 8000, then run:

```bash
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Routing is hash-based, so the production
build (`npm run build`) can be served as static files without rewrite rules.

The actor field and role selector in the header only choose the `X-Role` / `X-Actor`
headers sent with each request — they are a development seam for exercising authorization,
not a login. The server is what enforces it. No credentials or secrets are ever handled
here: devices reference a credential profile by id, and there is no password field.

See `docs/phase-3-implementation.md` for the full feature and usage guide.
