# Network Switch Backup Automation

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

## Mock SSH switch

To test without a physical device, start the mock switch in another terminal:

```bash
python tests/mock_switch.py
```

It listens on `127.0.0.1:2222` with username `admin` and password `admin`.
Use `127.0.0.1:2222` in `data/devices.csv`.

## Configuration

`config.json` stores the settings editable in the Web UI. Environment
variables such as `BACKUP_ROOT`, `DEVICES_FILE`, `LOG_FILE`, and
`REPORT_COMMANDS` can still override the local configuration.

## License

This project is intended for educational and internal network administration
use.
