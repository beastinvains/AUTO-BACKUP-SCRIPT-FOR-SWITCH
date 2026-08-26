# Phase 3 — Network topology visualization and the complete management UI

## Delivered scope

Phase 3 turns the platform into something an operator can actually run a network from. It adds
an evidence-based topology graph over the inventory Phase 1 discovers, named backup schedules on
top of the Phase 2 backup service, an event log over records the platform already writes, and a
single React web UI that covers every screen in the blueprint's Phase 3 list.

Nothing was redesigned. Discovery (Phase 1) and configuration backup/versioning (Phase 2) run
through the same services as before; Phase 3 reads their output and adds the missing management
surface around them. There is one backend, one device store, one backup implementation, one
scheduler and one frontend.

## What was added

**Topology** — `topology/normalization.py`, `topology/graph.py` and `topology/service.py` build a
`CONNECTED_TO` graph from the LLDP `neighbors` rows discovery already records. Nodes, edges,
per-device subgraphs, filters and evidence statistics are exposed under `/api/topology`.

**Inventory management** — `inventory/service.py` adds validated create / update / delete for
devices, plus a `summary` payload (inventory row + interface, neighbour and version counts + last
backup and last discovery timestamps) used by the topology drawer and the device page.

**Named backup schedules** — `schedule_service.py` and migration `0004_backup_schedules` replace
the single hard-coded daily window with schedule rows (hourly / daily / weekly, UTC, optional
device scope). `scheduler.py` is now only a clock: it asks `ScheduleService` what is due and lets
it call the Phase 2 `BackupService`.

**Event log** — `audit/query.py` merges audit records and backup jobs into one filterable feed
(date range, device, event type, status, free text) with secret-shaped keys and raw command output
stripped before the response is built.

**Dashboard** — `backend/dashboard.py` aggregates infrastructure, topology, backup and discovery
counters, including devices never backed up and devices whose last backup is older than
`STALE_BACKUP_DAYS` (7).

**React web UI** — `frontend/` is now the primary interface: dashboard, device list, device
detail, topology map, backups, schedules, configuration history, logs, and explicit placeholders
for the later-phase screens. The Flask templates are no longer the product UI.

**Multi-device mock lab** — `tests/lab_estate.py` describes six Junos personas whose LLDP tables
cross-reference each other, `tests/mock_lab.py` serves them over SSH (one port per device, reusing
`tests/mock_switch.py` rather than adding a second SSH implementation), and `scripts/lab_setup.py`
registers and discovers them through the existing Phase 1 service. This is how the map was
exercised without hardware; see [docs/mock-lab-guide.md](mock-lab-guide.md).

## How a link becomes an edge

The graph is built only from what devices reported. The rules live in `topology/graph.py` and are
unit-tested with fixtures:

- an edge requires a local interface **and** a remote identity — a neighbour entry missing either
  is counted in `insufficient_evidence` and left undrawn;
- a reported neighbour is correlated to inventory by hostname and normalized chassis ID; if two or
  more devices match, the identity is recorded in `ambiguous_identities` and **no edge is created**;
- a neighbour that cannot be matched at all becomes an explicit `external` (unmanaged) node rather
  than being merged into a lookalike device;
- confidence rises only through corroboration, never through repetition:
  `0.95` both endpoints managed and each reported the other, `0.7` both managed but only one side
  reported it, `0.4` the far endpoint is not in inventory;
- `interface_evidence` is `complete` when both interface names are known and `partial` otherwise.

`CONNECTED_TO` is the only relationship implemented. `HOSTS`, `RUNS`, `DEPENDS_ON`, `ROUTES_TO`
and `BALANCES_TO` are deferred, though the payload shape already carries a type field.

## One source of truth

| Concern | Phase 3 location |
| --- | --- |
| Device rows, interfaces, neighbours | `devices` / `interfaces` / `neighbors` (Phase 1 tables — no topology store) |
| LLDP correlation and graph building | `topology/normalization.py`, `topology/graph.py` |
| Topology queries | `topology/service.py` — four grouped aggregate queries regardless of estate size |
| Device add / edit / delete | `inventory/service.py` |
| Configuration backup execution | `backup_service.py` (unchanged from Phase 2) |
| When a backup runs | `schedule_service.py`; `scheduler.py` only polls for due rows |
| Event feed | `audit/query.py` over `audit_logs` + `backup_jobs` |
| Dashboard counters | `backend/dashboard.py` |
| HTTP surface | `backend/app.py` — routes only, no vendor commands |
| Web UI | `frontend/src` (Vite + React + TypeScript) |

A scheduled backup and a manual backup are the same code path and land in the same job table;
`requested_by` (`schedule:<name>` versus an actor) is how you tell them apart afterwards. The
topology service never opens a configuration artifact — only metadata.

## Database changes

Alembic revision `0004_backup_schedules` adds `backup_schedules` (`name` unique, `device_ids` JSON
scope, `frequency`, `run_at`, `day_of_week`, `enabled`, `next_run_at`, `last_run_at`,
`last_status`, `last_job_id`, `created_at`/`created_by`/`updated_at`) with an index on
`next_run_at` so "what is due" is a cheap query.

That is the only schema change Phase 3 needs. Topology adds no tables — it reads the Phase 1
inventory. (`0003_device_ssh_port`, which persists a per-device management port, arrived with the
Phase 2 work and is applied by the same `alembic upgrade head`.)

A second revision, `0005_device_endpoint_identity`, followed from testing the map without hardware:
`0001_inventory` made `management_ip` unique on its own, which is only true while every device sits
on port 22. A device is the endpoint it is reached on, so the constraint is now the
`(management_ip, management_port)` pair, with a non-unique index left on the address. That is what
lets several devices share one address — a mock lab on one host, port-forwarded appliances behind a
jump host, an out-of-band console server — and it is required by the lab described in
[docs/mock-lab-guide.md](mock-lab-guide.md).


## API surface

Phase 3 endpoints, in addition to the Phase 1 discovery and Phase 2 backup routes:

| Endpoint | Role required | Purpose |
| --- | --- | --- |
| `GET /api/topology` | any | Full graph: `nodes`, `edges`, `stats`, `filters` |
| `GET /api/topology/nodes` | any | Nodes + stats only |
| `GET /api/topology/edges` | any | Edges + stats only |
| `GET /api/topology/devices/{device_id}` | any | One device's immediate neighbourhood |
| `GET /api/topology/{site}` | any | Site-scoped graph |
| `GET /api/devices/{device_id}/summary` | any | Inventory row + counts + last backup/discovery |
| `POST /api/devices` | `admin` | Add device (201) |
| `PUT /api/devices/{device_id}` | `admin` | Edit device |
| `DELETE /api/devices/{device_id}` | `admin` | Delete device, reports versions removed |
| `POST /api/devices/{device_id}/discovery` | `admin`/`operator` | Re-run Phase 1 discovery for one device |
| `GET /api/schedules`, `GET /api/schedules/{id}` | any | List / read schedules |
| `POST /api/schedules` | `admin` | Create schedule (201) |
| `PUT /api/schedules/{id}` | `admin` | Update schedule |
| `POST /api/schedules/{id}/enabled?enabled=` | `admin` | Enable / disable |
| `DELETE /api/schedules/{id}` | `admin` | Delete schedule (204) |
| `POST /api/schedules/{id}/run` | `admin`/`operator` | Run off-cycle (202), same `BackupService` |
| `GET /api/scheduler` | any | Runner state: `running`, `tick_seconds`, `due_now` |
| `GET /api/logs` | any | Event feed: `start`, `end`, `device_id`, `category`, `status`, `search`, `limit` (1–1000) |
| `GET /api/logs/options` | any | Valid categories, statuses and device names for the filters |
| `GET /api/dashboard` | any | Aggregated counters |

The topology filter parameters `site`, `vendor`, `device_type` and `status` are shared by every
topology route and applied before the graph is built. `/api/topology/{site}` is declared last so
`/nodes` and `/edges` are never parsed as a site name.

Authorization uses the same header seam as Phase 2: `X-Role` must be `admin` (device and schedule
changes) or `admin`/`operator` (backups, configuration reads, discovery), and `X-Actor` is
recorded in the audit trail. A read-only role can view permitted information and receives 403 on
every administrative action.

## The React application

`frontend/` is a Vite + React + TypeScript app. Routing is hash-based (`#/devices/<id>/interfaces`),
which needs no server rewrite rules when the built bundle is served as static files.

| Route | Screen |
| --- | --- |
| `#/dashboard` | Infrastructure, topology, backup and discovery counters; ambiguous-identity notice |
| `#/devices` | Inventory list, filters, multi-select backup, add / edit / delete / discover |
| `#/devices/<id>[/tab]` | One device: `overview`, `interfaces`, `neighbors`, `backups` |
| `#/topology` | Network map, evidence counters, node and edge detail drawers |
| `#/backups` | Job history with per-device results; "Back up now" for all or selected devices |
| `#/schedules` | Schedule list, create / edit / enable / disable / delete / run now, runner state |
| `#/configurations[/<id>]` | Phase 2 version history, two-version compare, deterministic diff |
| `#/logs` | Filterable event feed with per-row expandable details |
| `#/alerts`, `#/ai`, `#/settings` | Explicit placeholders for later phases |

Supporting modules: `api.ts` (one client; identity headers are attached centrally so no call site
can forget them), `types.ts` (every payload shape), `format.ts`, `hooks.ts` (`useHashRoute`,
`useAsync`, `usePolling`), `components/ui.tsx`, `components/layout.ts` (deterministic graph
layout), `components/TopologyMap.tsx`, `components/DeviceDrawer.tsx`, `components/DeviceForm.tsx`.

The map supports pan, zoom, fit-to-view, node and edge selection, hover interface labels, an
"always show interfaces" toggle, keyboard focus on nodes, and a legend distinguishing managed from
unmanaged nodes and corroborated from one-sided links. Layout is deterministic — the same graph
always draws the same way, because every ordering decision falls back to the node id.

Status is never communicated by colour alone: every status pill carries a glyph and the status
word, and one-sided links are dashed as well as differently coloured.

## Security controls

- The Add/Edit Device form has no password field, by design. `DeviceInput` uses
  `extra="forbid"`, so a client that posts a `password` field gets a 422 instead of having the
  value silently accepted; the device references a credential profile by id, and
  `credentials_reference_id` is rejected if it contains `password`, `secret`, `passphrase` or
  `private_key`.
- The browser never receives credentials, SSH keys or environment configuration. The API returns
  credential *references* only.
- Log details are filtered server-side: secret-shaped keys and the bulk `raw` / `configuration` /
  `output` / `content` fields are dropped before the response, and the UI keeps details collapsed
  by default.
- Configuration content is redacted before it is stored, so version views and diffs cannot leak
  secrets that were never written.
- Administrative actions are gated by role on the server. The UI hides controls a role may not
  use and shows a read-only notice, but that is convenience — the server is the enforcement point.
- Delete asks for confirmation and reports how many configuration versions were removed.

## Run it locally

Install dependencies and apply migrations:

    .venv/bin/pip install -r requirements.txt
    .venv/bin/alembic upgrade head

Start the API (it also starts the schedule runner, which is inert until a schedule exists):

    .venv/bin/uvicorn backend.app:app --reload

Start the web UI in a second terminal:

    cd frontend
    npm install
    npm run dev

Open `http://127.0.0.1:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`, so no CORS
configuration is needed in development; the API also allows the Vite origin directly for a
production build.

For a static build:

    cd frontend
    npm run build

The CLI still works for headless use — `python app.py --backup-now` runs one backup immediately,
`python app.py --schedule` keeps running and executes stored schedules. Both go through the same
`BackupService`.

### Without any hardware

The topology map needs several devices that report each other over LLDP, so the single mock switch
cannot demonstrate it. `tests/mock_lab.py` serves a six-device estate — one SSH port each — from
this machine or from any spare machine on the LAN, and `scripts/lab_setup.py` registers and
discovers it through the existing Phase 1 service:

    python tests/mock_lab.py --host 0.0.0.0                 # on the lab machine
    .venv/bin/python scripts/lab_setup.py --host <lab-ip>    # on this machine

The estate's evidence is deliberately uneven, so every graph outcome appears: corroborated links,
single-sided links, unmanaged neighbours, partial interface evidence and a refused ambiguous
identity. A console command (`drift <device>`) changes a running configuration so the next backup
produces a real diff, and `down <device>` closes a port so a job goes `PARTIAL`.
[docs/mock-lab-guide.md](mock-lab-guide.md) is the walkthrough.


## Use it

**Set your role.** The header has an actor field and a role selector (`admin`, `operator`,
`viewer`). This is a development seam for exercising authorization, not a login: it only chooses
the `X-Role` header sent to the API. Pick `admin` to manage devices and schedules.

**Add a device.** Devices → *Add device*. Enter name, management IP, port, type, vendor, site and
the credential reference — never a password. Tick "Run discovery after saving" to have the new
device discovered immediately through the existing Phase 1 discovery service.

**Discover.** Devices → *Discover* on any row runs discovery for that device and refreshes its
interfaces, neighbours and health. Topology edges appear only after discovery has recorded LLDP
neighbours.

**Read the map.** Topology shows the graph with counters underneath: managed devices, unmanaged
neighbours, connections, connections confirmed by both ends, unresolved neighbours, and neighbour
entries with insufficient evidence (no edge drawn). Filter by site, vendor, device type or status
— filtering happens on the server. Click a node for its identity, status, counts and links to the
full device page; click a link for both interface names, whether both ends corroborated it, the
confidence value and the underlying observations. Ambiguous identities are listed in a notice
above the map, explaining that no connection was guessed.

**Back up now.** Backups → *Back up now* runs every device, or select devices first to narrow the
scope. The job table refreshes while a job is running and expands to per-device results with
`configuration changed` / `no change`, the version id and the duration. Failures are per device;
the job status becomes `PARTIAL`.

**Schedule backups.** Schedules → *Create schedule*. Choose hourly, daily or weekly, a UTC run
time, and optionally a device scope (select none for every managed device at run time). *Run now*
executes a schedule off-cycle through the same backup path, so watch it on the Backups page. The
metrics row shows whether the runner is up, its tick interval, and how many schedules are due.

**Compare configurations.** Configuration history → pick a device. Versions are listed with
timestamp, SHA-256, size, status, retention state and parent version. The two most recent versions
are pre-selected; press *Compare* for the deterministic added/removed/unchanged diff, or *View* to
read a stored version. No model interprets or summarizes the change.

**Investigate.** Logs filters discovery, backup, schedule, device, authentication and system
events by date range, device, event type, status and free text. Expand a row for its structured
details.

## What was verified

The backend suite runs offline against mock Junos output — no network hardware is required:

    .venv/bin/python -m unittest discover -s tests -t .

Result: **95 tests, OK.** Phase 3 contributed 76 of them —
`tests/test_phase3_topology.py` (21) covers correlation, ambiguity refusal, external nodes,
confidence tiers, interface evidence, filters and statistics; `tests/test_phase3_api.py` (39)
covers the topology routes, inventory CRUD and its validation (including the rejection of a posted
password and the endpoint-identity rule), schedules, the scheduler status, the log feed and its
redaction, and the dashboard; `tests/test_lab_estate.py` (16) drives the mock lab's six personas
through the real adapter parsers and the real graph builder, so the claims in
[docs/mock-lab-guide.md](mock-lab-guide.md) are checked rather than asserted. The remaining 19 are
the pre-existing Phase 1 (6), Phase 2 (3) and legacy/health tests (10), all still passing.
`tests/asgi_client.py` drives the ASGI app directly because `httpx` — and therefore FastAPI's
`TestClient` — is not installed in this environment.

The frontend was type-checked and built:

    cd frontend
    ./node_modules/.bin/tsc -b --force    # exit 0, no diagnostics
    npm run build                         # 32 modules transformed, dist/ written

The full flow was also run over real SSH against the mock lab, on one host with six ports: six
devices discovered `success`; topology stats identical to the offline expectations (6 devices, 3
unmanaged neighbours, 8 links, 2 corroborated, 3 unresolved, 0 insufficient evidence, `dist-sw01`
reported ambiguous); a backup job `SUCCESS`, an immediate re-run reporting `no change` for every
device, then `drift dist-sw01.dc-a.lab` followed by a third backup reporting
`configuration changed` for that device alone with a one-line deterministic diff
(`set vlans GUEST vlan-id 30`). The stored artifact for that device contained neither of the two
password hashes nor the SNMP community string present in the device's own output. Registering a
device nothing listens for produced one `failed` result and a `partial` job.

**Not verified here:** nothing was run against real network hardware, and the UI was not exercised
by an automated browser test — there is no assertion about rendered pixels, drag behaviour or
click paths beyond the type checker and a successful production build. The screens were written
against payload shapes read out of the Python source, and the RBAC behaviour they rely on is
covered by the API tests.

## Known limitations

The topology map is hand-drawn SVG rather than React Flow or Cytoscape.js as the phase brief
suggested: this environment has no package-registry access, so neither library could be installed,
and shipping a CDN dependency would have contradicted the "no CDN UI" constraint. The map
implements the behaviour the brief actually requires — pan, zoom, fit, selection, interface labels,
non-colour-dependent status — and the swap-in point is isolated to
`frontend/src/components/TopologyMap.tsx` plus `components/layout.ts` if a library is added later.

Other limits: discovery still runs synchronously in-process; the graph layout is a deterministic
BFS by component and depth, not a force-directed layout, so very dense estates will look crowded;
the log feed is a query over existing records rather than a streaming pipeline; the role selector
is not authentication, and real identity, alerting, AI assistance and platform settings are
deferred to their own phases. Legacy Flask views and the old CLI report helpers are still present
in the repository for compatibility, but they are no longer the product UI.
