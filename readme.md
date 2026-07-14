# Juniper Switch Backup Automation

## Overview

Juniper Switch Backup Automation is a Python-based utility that automatically connects to multiple Juniper switches over SSH, collects configuration and operational information, and stores the results in a structured directory hierarchy.

The project is designed for network administrators who want to automate switch backups and maintain organized records for auditing, troubleshooting, and disaster recovery.

---

# Features

- Backup multiple Juniper switches
- SSH connection using Netmiko
- Read switch inventory from CSV
- Automatic Year → Month → Day folder creation
- Separate folder for each switch
- Single timestamped backup file per switch
- Detailed logging
- Continues even if one switch fails
- Compatible with Windows and Linux
- Can be scheduled using Task Scheduler or Cron
- Supports OneDrive synchronization

---

# Project Structure

```
JuniperBackup/
│
├── backup.py
├── config.py
├── devices.csv
├── requirements.txt
├── README.md
├── backup.log
│
└── Backups/
    │
    ├── 2026/
    │
    │   └── 07-July/
    │
    │       └── 2026-07-13/
    │           │
    │           ├── CoreSW/
    │           │   └── backup_2026-07-13_02-00-05.txt
    │           │
    │           ├── AccessSW1/
    │           │   └── backup_2026-07-13_02-01-10.txt
    │           └── AccessSW2/
    │               └── backup_2026-07-13_02-02-30.txt
```

---

# Folder Structure

The backup folder is organized by date.

```
Backups
    ↓
Year
    ↓
Month
    ↓
Day
    ↓
Switch Name
    ↓
Timestamped Backup File
```

Example

```
Backups
└── 2026
    └── 07-July
        └── 2026-07-13
            └── CoreSW
                └── backup_2026-07-13_02-00-05.txt
```

This structure makes it easy to locate backups for a specific switch on a specific day.

---

# Commands Collected

Each generated backup file contains a clear header followed by all requested Junos command outputs, labeled in order:

- show configuration | display set | no-more
- show spanning-tree interface | no-more
- show spanning-tree bridge | no-more
- show lldp neighbors | no-more
- show vlan brief | no-more
- show interfaces terse | no-more
- show arp no-resolve | no-more
- show arp no-resolve state | no-more
- show arp no-resolve reference-count | no-more
- show virtual-chassis vc-port | no-more
- show lacp interface | no-more
- show version | no-more
- show chassis hardware | no-more
- show chassis mac-addresses | no-more
- show chassis environment | no-more
- show system uptime | no-more
- show configuration | display set | match ntp
- show ntp status

---

# Prerequisites

- Python 3.10 or later
- SSH enabled on Juniper switches
- Network connectivity to switches

---

# Installation

Clone or copy the project.

Install dependencies.

```
pip install -r requirements.txt

for linex you can use 
sudo apt install python3-xyz
```

---

# Configure Backup Location

Edit `config.py`.

Example

```python
BACKUP_ROOT = r"C:\Users\Backup\OneDrive\NetworkBackups"
```

Linux Example

```python
BACKUP_ROOT = "/home/backup/NetworkBackups"
```

---

# Configure Switch Inventory

Create a file named `devices.csv` in the project folder.

The script expects the file to contain a CSV header like this:

```csv
hostname,ip,username,password
```

Example

```csv
hostname,ip,username,password
CoreSW,192.168.1.10,backup,password123
AccessSW1,192.168.1.11,backup,password123
AccessSW2,192.168.1.12,backup,password123
```

Important notes:
- The file name must be exactly `devices.csv`
- The first row must contain the column names: `hostname,ip,username,password`
- Each following row represents one switch
- Keep the password in the `password` column only if you are comfortable storing it in plain text locally

---

# Running the Backup

Run the script.

```
python backup.py
```

The script will

1. Read all switches from devices.csv
2. Connect using SSH
3. Execute all configured commands
4. Save all outputs into one timestamped file per switch
5. Add a clear header with device name, IP, and timestamp inside the file
6. Disconnect
7. Continue to the next switch
8. Generate backup.log

---

# Logging

The project creates a log file named

```
backup.log
```

Example

```
2026-07-13 02:00:05 INFO CoreSW SUCCESS
2026-07-13 02:00:10 INFO AccessSW1 SUCCESS
2026-07-13 02:00:13 ERROR AccessSW2 Authentication Failed
```

Logs are useful for

- Troubleshooting
- Verifying successful backups
- Identifying failed devices
- Auditing backup operations

---

# Scheduling

## Windows

Use Task Scheduler.

Run

```
python C:\JuniperBackup\backup.py
```

daily.

---

## Linux

Use Cron.

```
0 2 * * * python3 /home/backup/JuniperBackup/backup.py
```

This runs every day at 2:00 AM.

---

# Future Improvements

Possible enhancements include:

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