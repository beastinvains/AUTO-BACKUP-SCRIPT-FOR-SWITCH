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
- Separate output file for each command
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
    │           │   ├── configuration.cfg
    │           │   ├── version.txt
    │           │   ├── system_information.txt
    │           │   ├── interfaces.txt
    │           │   ├── lldp_neighbors.txt
    │           │   ├── chassis_hardware.txt
    │           │   └── virtual_chassis.txt
    │           │
    │           ├── AccessSW1/
    │           └── AccessSW2/
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
Command Output Files
```

Example

```
Backups
└── 2026
    └── 07-July
        └── 2026-07-13
            └── CoreSW
                ├── configuration.cfg
                ├── version.txt
                ├── interfaces.txt
                ├── lldp_neighbors.txt
                └── ...
```

This structure makes it easy to locate backups for a specific switch on a specific day.

---

# Commands Collected

| File | Junos Command | Purpose |
|------|---------------|----------|
| configuration.cfg | show configuration \| display set | Configuration backup |
| version.txt | show version | Software version |
| system_information.txt | show system information | Hostname, serial number, uptime |
| interfaces.txt | show interfaces terse | Interface status |
| lldp_neighbors.txt | show lldp neighbors detail | Physical neighbor information |
| chassis_hardware.txt | show chassis hardware | Hardware inventory |
| virtual_chassis.txt | show virtual-chassis | Virtual Chassis information |

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
4. Save each command output into a separate file
5. Disconnect
6. Continue to the next switch
7. Generate backup.log

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