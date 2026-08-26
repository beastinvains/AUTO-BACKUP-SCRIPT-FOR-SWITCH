# Mock lab guide — run the whole platform without network hardware

You do not need a switch, a router or a firewall to exercise this platform. `tests/mock_lab.py`
serves a small estate of six mock Junos devices, one SSH port each, from any machine on your LAN.
The platform then discovers them, backs them up, versions and diffs their configurations, runs
schedules against them, and draws the topology map from the LLDP tables they report.

The single-device mock (`tests/mock_switch.py`) is still there and unchanged — it is what the
Phase 2 smoke test drives. It cannot demonstrate topology, because a map needs several devices
that *talk about each other*. That is the gap this lab fills.

This is not a Junos emulator. Each device answers a fixed set of commands with realistic canned
output, which is exactly what the adapter parses. Nothing here is a real credential: the estate
accepts one well-known development login, `admin` / `admin`, that exists only inside the lab.

## What you need

| Machine | Needs |
| --- | --- |
| **Lab machine** (the "devices") | Python 3.10+, `pip install paramiko`, and four files from this repository: `tests/mock_lab.py`, `tests/lab_estate.py`, `tests/mock_switch.py` and `tests/mock_data.py`. Copy them into one directory (or just copy the whole `tests/` directory, or clone the repository). The platform, its database and the rest of `requirements.txt` are *not* needed here. |
| **Platform machine** | This repository, its virtualenv, and network reach to the lab machine on TCP 2201–2206. |

Both can be the same machine (use `--host 127.0.0.1`) if you just want to see it work — the LAN
split only matters when you want the platform to talk to something that is genuinely off-box.

Ports start at 2201, so nothing needs root.

## The estate

Six devices, deliberately uneven, because that is what the topology rules are for:

| Device | Port | Model | Site | What it demonstrates |
| --- | --- | --- | --- | --- |
| `core-rtr01` | 2201 | mx204 | dc-a | Corroborated link to dist-sw01.dc-a, single-sided link to the firewall, an unmanaged ISP neighbour |
| `dist-sw01.dc-a.lab` | 2202 | ex4650-48y | dc-a | Both ends of two corroborated links |
| `access-sw01` | 2203 | ex4300-48p | dc-a | A neighbour that advertises no port id — partial interface evidence |
| `access-sw02` | 2204 | ex2300-48p | dc-a | An uplink reported by short name only, which is ambiguous and gets refused; an unmanaged access point |
| `edge-fw01` | 2205 | srx345 | dc-a | LLDP disabled (`LLDP is not enabled`), so its link is only ever seen from one side |
| `dist-sw01.dc-b.lab` | 2206 | ex4650-48y | dc-b | A second site, for the site filter — and a second device answering to the name `dist-sw01` |

Every device has its own configuration, its own interfaces and descriptions, and its own drift
script, so backups and diffs differ per device.

## Step 1 — start the estate on the lab machine

Copy the four files (or the whole repository) across, then, from the directory holding them:

    pip install paramiko
    python mock_lab.py --host 0.0.0.0

From a full checkout the path is `python tests/mock_lab.py --host 0.0.0.0` instead.
`--host 0.0.0.0` is the default and is what makes it reachable from the LAN; bind to a specific
address if you prefer. It prints what is running and the exact command to use on the other side:

    Mock lab running: 6 devices on 0.0.0.0, ports 2201-2206
    Login: admin/admin

    DEVICE                  PORT  STATE MODEL        SITE   CHANGES
    core-rtr01              2201  up    mx204        dc-a   0
    dist-sw01.dc-a.lab      2202  up    ex4650-48y   dc-a   0
    access-sw01             2203  up    ex4300-48p   dc-a   0
    access-sw02             2204  up    ex2300-48p   dc-a   0
    edge-fw01               2205  up    srx345       dc-a   0
    dist-sw01.dc-b.lab      2206  up    ex4650-48y   dc-b   0

    Register this estate with the platform:
      python scripts/lab_setup.py --host 192.168.1.42 --base-port 2201

Useful flags: `--base-port 3301` moves the whole block (if 2201–2206 are taken), and
`--only core-rtr01,dist-sw01.dc-a.lab` runs a subset.

If the lab machine has a host firewall, open the block — for example on Ubuntu:

    sudo ufw allow 2201:2206/tcp

Leave this terminal open: it is also the lab console (see below). Under `nohup` or with piped
stdin it prints `stdin is closed; serving without a console` and keeps serving.

## Step 2 — give the platform the lab login

The lab uses its own credential profile, `mock_lab`, so it can never collide with a real one.
On the platform machine:

    export MOCK_LAB_USERNAME=admin
    export MOCK_LAB_PASSWORD=admin

Or put those two lines in `.env`. Passwords are never stored in the database — devices store only
the profile name, and the profile is resolved from the environment at connection time. Do not
reuse this profile for anything real.

`scripts/lab_setup.py` refuses to run without it and prints these exact two lines if the profile
is missing.

## Step 3 — bring the schema up to date

The lab puts six devices on **one address**, which requires migration `0005_device_endpoint_identity`
— a device is identified by the `(management_ip, management_port)` pair, not the address alone:

    .venv/bin/alembic upgrade head

If the database still has the old single-column unique constraint, `lab_setup.py` stops and says
so rather than failing halfway through discovery.

## Step 4 — register and discover the estate

    .venv/bin/python scripts/lab_setup.py --host 192.168.1.42

Use the lab machine's address. The script probes every port first, then runs the **existing**
Phase 1 discovery service — there is no second discovery path — and prints what came back. Add
`--with-unreachable` to also register a device nothing answers on, which is how the output below
was produced:

    Lab host 127.0.0.1, ports 2201-2206, credential profile 'mock_lab'
      core-rtr01             port  2201  open
      dist-sw01.dc-a.lab     port  2202  open
      access-sw01            port  2203  open
      access-sw02            port  2204  open
      edge-fw01              port  2205  open
      dist-sw01.dc-b.lab     port  2206  open
      spare-sw09             port  2291  closed

    Discovering...
      success  core-rtr01             32e0c13c-ad26-45d4-a427-99b1131527e5
      success  dist-sw01.dc-a.lab     a0863aa1-13cf-482b-8ecc-4c0ff1ebab72
      success  access-sw01            9cf168b6-040e-4930-a193-f47da2a126e8
      success  access-sw02            746e13c4-d8c0-4e23-bb3d-298b8dbe1af7
      success  edge-fw01              9cbd7d9f-3646-4799-a6bb-c34eaa2b1258
      success  dist-sw01.dc-b.lab     3d5cfc33-83d2-424b-bde2-83138567a23a
      failed   spare-sw09             NetmikoTimeoutException
    Discovery job partial: 6/7 devices

    Topology built from the LLDP evidence just collected:
      device_count           6
      external_count         3
      edge_count             8
      corroborated_edges     2
      unresolved_neighbors   3
      insufficient_evidence  0
      ambiguous_identities   dist-sw01

Discovery takes about **11 seconds per device** against the mock (netmiko's prompt-detection
timers, not the platform), so a first run is roughly a minute. Re-running is safe: discovery
upserts by management endpoint, so the estate is refreshed rather than duplicated. `--skip-discovery`
checks the environment and prints the plan without connecting.

## Step 5 — use the platform

    .venv/bin/uvicorn backend.app:app --reload     # API on 127.0.0.1:8000
    cd frontend && npm run dev                     # UI on 127.0.0.1:5173

Open `http://127.0.0.1:5173` and set the role selector in the header to `admin` (it is a
development seam for authorization, not a login — see
[docs/phase-3-implementation.md](phase-3-implementation.md)). Then:

1. **Devices** — six rows, all with the same management IP and different ports, each with its own
   model, serial, OS version, interfaces, neighbours and health.
2. **Topology** — the map below. Click a node for identity and counts; click a link for both
   interface names, whether both ends corroborated it, the confidence value and the raw
   observations. Filter by site: `dc-b` narrows to one device and zero links, because its only
   peer is filtered out.
3. **Backups → Back up now** — six devices backed up; every result is `configuration changed` the
   first time. Run it again and every result becomes `no change`, because the content hash is
   identical.
4. **Drift, then back up again** — in the lab console type `drift dist-sw01.dc-a.lab`, then run
   another backup. That device reports `configuration changed`, the others still report `no change`.
5. **Configuration history** — pick that device, select the two newest versions, press *Compare*.
   The diff is deterministic added/removed/unchanged, with the exact line that changed.
6. **Schedules** — create an hourly or daily schedule and press *Run now*; it executes through the
   same `BackupService` and shows up on the Backups page.
7. **Logs** — the discovery, backup and schedule events for everything above, including the
   failure if you registered the unreachable device.

## What the map should show, and why

These numbers are not decoration; they are what the evidence supports.

| Counter | Value | Why |
| --- | --- | --- |
| Managed devices | 6 | The estate |
| Unmanaged neighbours | 3 | `isp-edge-rtr`, `ap-lobby-01` and a `dist-sw01` that could not be resolved |
| Connections | 8 | Drawn only where evidence exists |
| Confirmed by both ends | 2 | core ↔ dist-sw01.dc-a and dist-sw01.dc-a ↔ access-sw01, at confidence **0.95** |
| Unresolved neighbours | 3 | Reported neighbours that inventory does not contain, drawn to explicit external nodes at confidence **0.4** |
| Insufficient evidence | 0 | See below |

Single-sided links (`core-rtr01 → edge-fw01`, `dist-sw01.dc-b.lab → core-rtr01`) sit at confidence
**0.7**: real evidence from one end only, because LLDP is off on the far side.

`access-sw01 ↔ access-sw02` also sits at 0.7 with **partial** interface evidence — the neighbour
row carries a name but no port id, so one end of the link has no interface label. The map says
`partial` instead of inventing a port.

The interesting one is **ambiguity refusal**. `access-sw02` reports its uplink as `dist-sw01`, and
two devices answer to that short name. Rather than guess, the platform draws the uplink to an
unmanaged node at confidence 0.4 and lists `dist-sw01` in the "ambiguous identities" notice above
the map. There is no edge from `access-sw02` to either real `dist-sw01`.

**`insufficient_evidence` stays 0 on purpose.** That counter guards neighbour rows recorded with
neither a name nor a chassis id, and no device output can honestly produce one — every LLDP row
here carries at least a chassis id. Faking it would mean writing device output that no device
emits, so it is covered by `tests/test_phase3_topology.py` at the graph level instead.

Also worth knowing: the serial numbers in this estate are serial numbers, not chassis MACs, so
managed devices are correlated by the hostname they advertise and never by the MAC in the Chassis
Id column. That is the same situation as a real estate.

## The lab console

While `tests/mock_lab.py` runs, its terminal accepts:

| Command | Effect |
| --- | --- |
| `list` | Table of devices, ports, up/down state and how many config changes each has taken |
| `drift <name>` | Change that device's running configuration, so the next backup has a real diff. Short names work (`drift access-sw01`) |
| `drift all` | Change every device |
| `down <name>` | Stop listening on that port — the platform records a connection failure and the job becomes `PARTIAL` |
| `up <name>` | Start listening again |
| `quit` | Stop the lab |

Drift is scripted per device and reports what it did, for example:

    lab> drift dist-sw01.dc-a.lab
    dist-sw01.dc-a.lab: GUEST VLAN 30 created
    lab> drift dist-sw01.dc-a.lab
    dist-sw01.dc-a.lab: VOICE VLAN renumbered from 20 to 120

The second one is a *replacement*, not an addition, so the diff shows one removed and one added
line. When a device's scripted changes run out it keeps producing new, distinct configurations, so
`drift all` in a loop never stops producing real diffs.

`down` is the honest way to see failure handling: the device's next discovery or backup fails with
`NetmikoTimeoutException`, the job status becomes `PARTIAL`, and the other devices still succeed.

## What was verified with this lab

Run against the estate over real SSH, on this repository:

- Six devices discovered `success`, all on one address with ports 2201–2206 — the endpoint
  identity rule working end to end.
- Topology stats exactly as the table above, matching what `tests/test_lab_estate.py` predicts
  from the same fixtures without a network.
- Backup job `SUCCESS` for six devices; an immediate re-run reported `no change` for all of them.
- `drift dist-sw01.dc-a.lab` → `GUEST VLAN 30 created`; the next backup reported
  `configuration changed` for that device only, with a diff of `{added: 1, removed: 0, unchanged: 27}`
  and the added line `set vlans GUEST vlan-id 30`.
- The stored configuration artifact contained no secret material — no password hash and no SNMP
  community string, both of which are present in the mock's raw output.
- `--with-unreachable` produced one `failed` result and a `partial` job, as shown above.

The offline suite covers the fixtures themselves so this guide's claims are checked rather than
asserted:

    .venv/bin/python -m unittest discover -s tests -t .

`tests/test_lab_estate.py` (16 tests) drives every persona through the real adapter parsers and
the real graph builder: that each answers every command the adapter issues, that models, serials,
health and interface descriptions parse, that configurations are unique per device, that all three
confidence tiers, the partial-interface link, the external nodes and the ambiguity refusal come out
as described, and that drift really changes the configuration.

## Troubleshooting

**Every port reports `closed`.** The lab is bound to `127.0.0.1` on the other machine (use
`--host 0.0.0.0`), or a host firewall is blocking 2201–2206, or the two machines are on different
subnets. Check with `nc -vz <lab-ip> 2201` from the platform machine.

**`still has a single-column unique constraint on devices.management_ip`.** Run
`.venv/bin/alembic upgrade head`. Six devices cannot share one address until `0005` is applied.

**`No credentials for profile 'mock_lab'`.** Export the two variables from step 2 in the same
shell that runs `lab_setup.py`, `uvicorn` and the scheduler.

**Discovery is slow.** ~11 s per device is expected; it is netmiko's prompt and read timers against
a mock that answers instantly.

**`NetmikoTimeoutException` for a device you expected to work.** It is `down` in the lab console,
or its port is blocked. `up <name>` and re-discover.

**Nothing appears on the topology map.** Edges come only from LLDP neighbours recorded by
discovery. Discover the devices first; a device added by hand and never discovered has no evidence
and therefore no links.

**Start over.** Stop the API, delete the development database (`phase1.db`) and the stored
artifacts, then `alembic upgrade head` and re-run `lab_setup.py`. The artifact root is
`BACKUP_ROOT`, or `backup_directory` in `config.json`, defaulting to `~/NetworkBackups`.

To keep your normal database and artifacts untouched, give the lab its own before running steps
3–5:

    export DATABASE_URL=sqlite:///./lab.db
    export BACKUP_ROOT=./lab-artifacts

Every command in steps 3–5 — `alembic`, `lab_setup.py`, `uvicorn` — must see both variables, or
they will read a different database from the one you migrated.

## What this lab cannot show you

Real hardware quirks — vendor-specific command variations, slow or truncated output, authentication
failures, flapping links. The mock answers cleanly and immediately. It also cannot produce
`insufficient_evidence` (above), it does not implement relationships other than `CONNECTED_TO`, and
the role selector is not authentication. Nothing in this guide has been run against real network
hardware, and no claim here depends on it.
