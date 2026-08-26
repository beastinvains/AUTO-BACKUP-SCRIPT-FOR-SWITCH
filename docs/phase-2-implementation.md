# Phase 2 — Configuration backup, versioning and API integration

## Delivered architecture

The new configuration execution path is `BackupService`: select persisted inventory devices, call the Juniper adapter's allowlisted configuration command, normalize/redact, SHA-256 hash, create a version only if changed, write an immutable artifact, save metadata, and append an audit record. Device failures are isolated, yielding `SUCCESS`, `PARTIAL`, or `FAILED` batch jobs.

Local storage creates `YEAR/MM-Month/DD/DEVICE/configuration/VERSION.cfg`. Database metadata—not directory parsing—is authoritative. Artifact paths are sanitized and resolved below the configured root.

## Migration map

| Legacy concern | Phase 2 location |
| --- | --- |
| Juniper SSH/config command | `adapters/juniper/adapter.py` |
| Directory creation | `storage/local.py` |
| Backup orchestration/failure isolation | `backup_service.py` |
| Auditable actions | `audit_logs` metadata and redacted structured logging |
| Daily scheduler abstraction | `BackupScheduler` callback to `BackupService` |
| Daily reports/operational commands | retained legacy reporting compatibility, separate from config versions |

`app.py` is now a compatibility CLI wrapper over the same Phase 2 service. The old `backup.py` report helpers and Flask report UI are retained only for legacy daily-report access while the database-backed API is adopted. No existing backups are deleted.

## Database and API

Alembic revision `0002_configuration_backups` adds `configuration_versions`, `backup_jobs`, and `audit_logs`. Versions have parent id, SHA-256, URI, adapter/platform/parser metadata, size, status, and retention state.

- `GET/POST /api/backups`, `GET /api/backups/{job_id}`
- `GET /api/devices/{id}/configurations`
- `GET /api/devices/{id}/configurations/{version_id}`
- `GET /api/devices/{id}/configurations/{version_a}/diff/{version_b}`

Backup endpoints require `X-Role: admin` or `operator`; `X-Actor` records the caller. Artifacts are never served by filesystem path; credential values are excluded from response and audit data.

## UI, scheduler, and validation

The checked-in UI is Flask templates, not the React client named by Phase 0. Its reports remain compatibility views; Phase 2 UI consumers should use the API for job polling, version history, and deterministic added/removed/unchanged diffs. The scheduler remains a small abstraction and must invoke the same `BackupService` used by the API.

`tests/test_phase2_configuration.py` covers normalization/hash/diff and local storage traversal/immutability. This environment lacks installed runtime dependencies (`SQLAlchemy`, `pydantic`, `Flask`, and `pytest`), so install requirements then run `python3 -m unittest discover -v`.

For a Juniper lab: discover devices first, apply migration, start `uvicorn backend.app:app`, POST a backup with operator headers, poll its job, and compare two returned versions using a read-only account. S3 encryption, identity-provider integration, React implementation, and distributed workers remain future work.
