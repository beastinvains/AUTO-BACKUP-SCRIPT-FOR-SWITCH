# Phase 1 — Inventory and Juniper Discovery

## Implemented

Phase 1 adds a vendor-neutral device domain model, a read-only adapter contract, a Juniper/Junos Netmiko adapter, discovery-job isolation, SQLAlchemy inventory persistence, Alembic migration, seed configuration, structured safe logging and a thin FastAPI API.

The legacy backup CLI and Flask UI remain unchanged. Existing credentials.py is reused as the local development credential provider; the new inventory stores only credentials_reference_id.

## Intentionally not implemented

Cisco, AI/ML, configuration backup/versioning migration, automatic changes, approval workflows, VM/server discovery, advanced topology visualization, authentication and distributed workers are deferred. Phase 2 will move configuration backup/versioning behind the adapter boundary.

## Relevant structure

- core: normalized Device, Interface, Neighbor, Health and discovery target/result models.
- adapters: BaseDeviceAdapter and adapters/juniper/adapter.py. All Junos commands and parsing are here.
- discovery: seed loading and in-process, per-device-isolated jobs.
- inventory and database: repository, SQLAlchemy models, migration 0001_inventory.
- backend: FastAPI routes only; it contains no Junos commands.
- audit: structured discovery logging that filters secret-like fields.
- tests: mocked, offline Junos discovery fixtures and tests.

## Configure a device

Copy config/devices.example.yaml to config/devices.yaml. This private file is ignored by Git. It contains device identity, management address and credentials reference only:

    cp config/devices.example.yaml config/devices.yaml

Provide the referenced local development credentials using environment variables or .env:

    LAB_JUNIPER_USERNAME=readonly-user
    LAB_JUNIPER_PASSWORD=replace-me

Do not commit .env or devices.yaml. Use an account with only read-only operational permissions.

## Run locally

Install dependencies and start the API:

    .venv/bin/pip install -r requirements.txt
    .venv/bin/uvicorn backend.app:app --reload

Apply the PostgreSQL migration after setting DATABASE_URL / updating alembic.ini:

    .venv/bin/alembic upgrade head

For a development-only demonstration, the API creates the local SQLite schema at startup. PostgreSQL is the intended persistent deployment database.
scre
Submit a discovery job with an allowlisted Juniper target. The API accepts a JSON array of target objects at POST /api/discovery/jobs. Query GET /api/devices, GET /api/devices/{id}, and the interfaces, neighbors and health subroutes afterwards.

For a seed-driven local run, after creating config/devices.yaml and .env, use:

    .venv/bin/python scripts/discover.py

## How discovery works

The adapter connects through Netmiko using the credential reference, then runs only five fixed read-only Junos commands: show version, interfaces terse, interface descriptions, LLDP neighbors and system processes. Output is parsed into typed models. Connection and command errors are converted to safe categories. Each target is isolated, so a mixed batch is PARTIAL when some devices fail.

## Offline tests

No physical switch is needed:

    .venv/bin/python -m unittest discover -s tests

Fixtures emulate realistic Junos output and test model validation, Juniper identification/parsing, command allowlisting, failure isolation, job states, persistence and secret exclusion from logs.

## Known limitations

The initial parsers target common Junos text output; they should gain platform-specific fixtures and XML/JSON support later. Jobs execute synchronously in-process, inventory does not yet model topology relationships, and API authentication is not enabled for this local Phase 1 demo.
