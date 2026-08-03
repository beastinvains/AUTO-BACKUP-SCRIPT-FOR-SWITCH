# Network Switch Backup Automation

This application connects to Cisco and Juniper switches over SSH, runs backup commands, and saves one timestamped text file per switch.

## Install

Install Python 3.10 or newer, then install the required libraries:

```bash
python -m pip install -r requirements.txt
```

On Debian/Ubuntu Linux, install Python and pip if needed:

```bash
sudo apt install python3 python3-pip
```

## Add devices

Edit `data/devices.csv`. Do not put passwords in this file.

```csv
hostname,ip,vendor,credential_profile
CoreSW,192.168.1.10,juniper,hq
AccessSW1,192.168.1.11,cisco,branch
```

`vendor` must be `juniper` or `cisco`. `credential_profile` connects a device to credentials in `.env`.
Use the real management IP address of each switch. The included `10.0.0.1` and `10.0.0.2` entries are examples, not working devices.

## Add credentials

Create a file named `.env` in this project folder. You type the credentials into it once, using this exact naming pattern:

```env
HQ_USERNAME=backup-user
HQ_PASSWORD=replace-with-the-hq-password
BRANCH_USERNAME=backup-user
BRANCH_PASSWORD=replace-with-the-branch-password
```

The profile `hq` in `data/devices.csv` uses `HQ_USERNAME` and `HQ_PASSWORD`. The profile `branch` uses `BRANCH_USERNAME` and `BRANCH_PASSWORD`. Names are converted to uppercase by the program.

The program loads `.env` into its own environment when it starts, reads the matching username/password, and passes them to SSH. The credentials are not written into backup files or logs. `.env` is plain text, so protect the file and never share or commit it.

## Protect `.env`

Linux: run this inside the project folder. Only the account that owns the file can then read or change it.

```bash
chmod 600 .env
```

Windows: open **Command Prompt** in the project folder and run the following. Replace `YourWindowsUser` with your Windows sign-in name. It removes inherited access and grants access only to you.

```bat
icacls .env /inheritance:r
icacls .env /grant:r YourWindowsUser:(R,W)
```

If `.env` was ever committed or shared, change those device passwords afterwards.

## Run

Start the application:

```bash
python app.py
```

It asks you to choose one of these options:

1. **Run a backup now** — backs up every listed device immediately, then exits.
2. **Daily schedule** — keeps the program running and starts a backup every day at 02:00.

For unattended use, skip the question with an option:

```bash
python app.py --backup-now
python app.py --schedule
```

## Backup files and logs

By default backups are saved under `~/NetworkBackups` on Linux and `C:\Users\Backup\OneDrive\NetworkBackups` on Windows. The folder structure is:

```text
NetworkBackups / year / month / day / switch-name / backup_timestamp.txt
```

Logs are written to `logs/backup.log` and shown in the terminal. Settings such as backup location, timeout, and number of parallel connections can be changed using environment variables described in `config.py`.

## Daily operational report

Each backup run also creates or updates one `daily_report.json` file in the same date folder as that day's device backup folders. Existing `.txt` backup files are unchanged. The report holds structured operational command results for a future Web UI.

By default it collects these commands:

- Juniper: `show chassis environment | no-more`, `show version | no-more`
- Cisco: `show environment`, `show version`

Set `REPORT_COMMANDS` in `.env` to replace the list. The value must be one line of valid JSON:

```env
REPORT_COMMANDS={"cisco":["show version","show environment"],"juniper":["show version | no-more","show chassis environment | no-more"]}
```

Commands already collected by the normal backup are reused for the report and are not sent to the device a second time. A command failure is stored in `daily_report.json` without preventing the normal device backup from completing.

If a device accepts a connection but is not responding as an SSH server, the application waits 15 seconds before reporting an SSH banner error. Change this only for unusually slow devices:

```env
BANNER_TIMEOUT=30
```

- SSH key authentication
- Email notifications
- Configuration change detection
- Automatic ZIP compression
- Backup retention policy
- Parallel backups
- HTML summary report
- Hardware inventory export
- OneDrive API integration
- Restore automation

---

# License

This project is intended for educational and internal enterprise network administration purposes.
