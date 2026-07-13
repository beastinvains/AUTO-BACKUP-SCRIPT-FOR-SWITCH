import os
import logging
from datetime import datetime

import pandas as pd
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException
)

# -----------------------------
# CONFIGURATION
# -----------------------------
DEVICE_FILE = "devices.csv"

# Change this to your backup location
BACKUP_ROOT = r"C:\Users\Backup\OneDrive\NetworkBackups"
# Example Linux:
# BACKUP_ROOT = "/home/backup/NetworkBackups"

# -----------------------------
# CREATE MONTHLY FOLDER
# -----------------------------
today = datetime.now()

month_folder = today.strftime("%Y-%m")

backup_folder = os.path.join(BACKUP_ROOT, month_folder)

os.makedirs(backup_folder, exist_ok=True)

# -----------------------------
# LOGGING
# -----------------------------
logging.basicConfig(
    filename=os.path.join(BACKUP_ROOT, "backup.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("========== Backup Started ==========")

# -----------------------------
# READ DEVICE LIST
# -----------------------------
devices = pd.read_csv(DEVICE_FILE)

# -----------------------------
# LOOP THROUGH DEVICES
# -----------------------------
for index, row in devices.iterrows():

    device = {
        "device_type": "juniper_junos",
        "host": row["ip"],
        "username": row["username"],
        "password": row["password"],
    }

    hostname = row["hostname"]

    try:

        print(f"Connecting to {hostname}...")

        connection = ConnectHandler(**device)

        config = connection.send_command(
            "show configuration | display set"
        )

        filename = f"{hostname}_{today.strftime('%Y-%m-%d')}.cfg"

        filepath = os.path.join(
            backup_folder,
            filename
        )

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(config)

        connection.disconnect()

        print(f"{hostname} Backup Successful")

        logging.info(f"{hostname} - SUCCESS")

    except NetmikoAuthenticationException:

        print(f"{hostname} Authentication Failed")

        logging.error(f"{hostname} Authentication Failed")

    except NetmikoTimeoutException:

        print(f"{hostname} Timeout")

        logging.error(f"{hostname} Timeout")

    except Exception as e:

        print(f"{hostname} Error: {e}")

        logging.error(f"{hostname} {e}")

logging.info("========== Backup Finished ==========")

print("\nAll backups completed.")
