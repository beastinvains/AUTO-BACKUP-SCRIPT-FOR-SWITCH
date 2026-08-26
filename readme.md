# Network Switch Backup Automation

> Phase 2 adds database-backed immutable Juniper configuration versions and a
> FastAPI backup API. Legacy report/Flask views remain available during migration;
> see [Phase 2 implementation](docs/phase-2-implementation.md) for the current
> architecture and API workflow.

This project backs up Cisco and Juniper devices over SSH, writes device
backups and a daily JSON report, and provides a local Flask Web UI.

## Install

Use Python 3.10 or newer. From the project folder, create and activate a
virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with:

```bat
.venv\Scripts\activate
```

## Create the device inventory

Create the `data` folder if it does not exist:

```bash
mkdir -p data
```

Create `data/devices.csv` with this header and one row for each device:

```csv
hostname,ip,vendor,credential_profile
CoreSW,192.168.1.10,juniper,hq
AccessSW1,192.168.1.11,cisco,branch
```

The `ip` field may include a non-standard SSH port, for example
`127.0.0.1:2222`. The supported vendors are `cisco` and `juniper`.

You can also manage this list from the Web UI's **Devices** page.

## Create `.env`

Create a `.env` file in the project root. Each `credential_profile` from
`devices.csv` needs a matching username and password pair. Profile names are
converted to uppercase.

```env
HQ_USERNAME=backup-user
HQ_PASSWORD=replace-with-the-hq-password
BRANCH_USERNAME=backup-user
BRANCH_PASSWORD=replace-with-the-branch-password
```

For the mock switch, use:

```env
HQ_USERNAME=admin
HQ_PASSWORD=admin
```

Do not commit `.env`. On Linux, restrict it to your account:

```bash
chmod 600 .env
```

## Run a backup

Run one backup immediately:

```bash
python app.py --backup-now
```

Or keep the command-line application running on its daily schedule:

```bash
python app.py --schedule
```

Backup files and `daily_report.json` are placed below the configured backup
directory. The default is `~/NetworkBackups` on Linux.

## Run the Web UI

Start the local UI from the project root:

```bash
python -m webui.app
```

Open `http://127.0.0.1:5000`.

The dashboard can run a backup immediately and start the daily scheduler for
the current Web UI process. The **Settings** page stores the backup time,
directory, worker count, and retention preference in `config.json`. The
**Reports** page reads `daily_report.json`, and the **Logs** page reads the
existing application log file.

## Phase 2 configuration backups

Run Phase 1 discovery first so targets are present in the inventory database, then
apply Alembic migrations and start the FastAPI application:

```bash
alembic upgrade head
uvicorn backend.app:app --reload
```

An administrator or operator starts a backup with `POST /api/backups` using an
`X-Role: admin` (or `operator`) header and polls `GET /api/backups/{job_id}`. The
configuration history and deterministic diff endpoints are documented in
`docs/phase-2-implementation.md`. Use a read-only Juniper account.

## Mock SSH switch

To test without a physical device, start the mock switch in another terminal:

```bash
python tests/mock_switch.py
```

It listens on `127.0.0.1:2222` with username `admin` and password `admin`.
Use `127.0.0.1:2222` in `data/devices.csv`.

## Mock lab (several devices, topology)

One mock switch cannot demonstrate the topology map, which needs several devices
reporting each other over LLDP. `tests/mock_lab.py` serves a six-device estate — one
SSH port each, ports 2201-2206 — from this machine or from any spare machine on the
LAN, which only needs Python and `paramiko`:

```bash
python tests/mock_lab.py --host 0.0.0.0
```

Then register and discover the estate from the platform:

```bash
python scripts/lab_setup.py --host <ip-of-the-lab-machine>
```

`docs/mock-lab-guide.md` is the full walkthrough: credentials, migrations, the lab
console (`drift`, `down`, `up`), what the resulting topology should show and why, and
what the lab cannot demonstrate.

## Phase 2 smoke test

This project includes an end-to-end smoke test that exercises the real backup,
versioning, diff, and discovery flow against the existing mock Juniper switch.
It does not change production logic and uses a temporary SQLite database plus a
temporary backup root.

From the project root:

```bash
source .venv-1/bin/activate
python tests/phase2_smoke_test.py
```

The script does the following:

1. Starts or reuses the existing mock switch.
2. Creates a temporary test device record.
3. Triggers a configuration backup via the existing `BackupService`.
4. Verifies the backup succeeds.
5. Verifies a configuration version is created.
6. Verifies the configuration hash is stored.
7. Triggers a second backup with the same configuration.
8. Verifies no duplicate version is created.
9. Changes the mock config and triggers another backup.
10. Verifies a new config version and diff are created.
11. Verifies the Phase 1 discovery flow still works.
12. Cleans up only temporary test data.

Expected result:

```text
PHASE 2 END-TO-END SMOKE TEST PASS
```

If you want to run the API itself for a manual check, use:

```bash
source .venv-1/bin/activate
alembic upgrade head
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Then confirm:

```bash
curl http://127.0.0.1:8000/api/devices
```

This should return HTTP 200.

## Configuration

`config.json` stores the settings editable in the Web UI. Environment
variables such as `BACKUP_ROOT`, `DEVICES_FILE`, `LOG_FILE`, and
`REPORT_COMMANDS` can still override the local configuration.

## License

This project is intended for educational and internal network administration
use.
