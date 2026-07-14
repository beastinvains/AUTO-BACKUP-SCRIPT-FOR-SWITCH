import os
import logging
from datetime import datetime

import pandas as pd

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from config import BACKUP_ROOT

# -----------------------------------
# Date folders
# -----------------------------------

today = datetime.now()
backup_timestamp = today.strftime("%Y-%m-%d_%H-%M-%S")

year_folder = today.strftime("%Y")
month_folder = today.strftime("%m-%B")
day_folder = today.strftime("%Y-%m-%d")

backup_path = os.path.join(
    BACKUP_ROOT,
    year_folder,
    month_folder,
    day_folder
)

os.makedirs(backup_path, exist_ok=True)

# -----------------------------------
# Logging
# -----------------------------------

logging.basicConfig(
    filename=os.path.join(BACKUP_ROOT, "backup.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logging.info("========== Backup Started ==========")

# -----------------------------------
# Commands
# -----------------------------------

COMMANDS = [
    "show configuration | display set | no-more",
    "show spanning-tree interface | no-more",
    "show spanning-tree bridge | no-more",
    "show lldp neighbors | no-more",
    "show vlan brief | no-more",
    "show interfaces terse | no-more",
    "show arp no-resolve | no-more",
    "show arp no-resolve state | no-more",
    "show arp no-resolve reference-count | no-more",
    "show virtual-chassis vc-port | no-more",
    "show lacp interface | no-more",
    "show version | no-more",
    "show chassis hardware | no-more",
    "show chassis mac-addresses | no-more",
    "show chassis environment | no-more",
    "show system uptime | no-more",
    "show configuration | display set | match ntp",
    "show ntp status",
]

# -----------------------------------
# Read CSV
# -----------------------------------

devices = pd.read_csv("devices.csv")

success = 0
failed = 0

# -----------------------------------
# Loop through switches
# -----------------------------------

for _, row in devices.iterrows():

    hostname = row["hostname"]

    switch_folder = os.path.join(
        backup_path,
        hostname
    )

    os.makedirs(switch_folder, exist_ok=True)

    device = {
        "device_type": "juniper_junos",
        "host": row["ip"],
        "username": row["username"],
        "password": row["password"],
    }

    try:

        print(f"Connecting to {hostname}...")

        connection = ConnectHandler(**device)

        output_sections = []

        for index, command in enumerate(COMMANDS, start=1):

            try:

                output = connection.send_command(
                    command,
                    read_timeout=60
                )

            except Exception as e:

                output = f"Command Failed\n\n{e}"

            output_sections.append(
                f"===== Command {index}/{len(COMMANDS)}: {command} =====\n{output}\n"
            )

        combined_output = "\n".join([
            f"===== Junos Backup =====",
            f"Device: {hostname}",
            f"IP Address: {row['ip']}",
            f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}",
            f"=======================\n",
            *output_sections,
        ])

        file_name = f"backup_{backup_timestamp}.txt"

        file_path = os.path.join(
            switch_folder,
            file_name
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(combined_output)

        connection.disconnect()

        success += 1

        logging.info(
            f"{hostname} SUCCESS"
        )

        print(f"{hostname} Backup Complete")

    except NetmikoAuthenticationException:

        failed += 1

        logging.error(
            f"{hostname} Authentication Failed"
        )

        print(f"{hostname} Authentication Failed")

    except NetmikoTimeoutException:

        failed += 1

        logging.error(
            f"{hostname} Timeout"
        )

        print(f"{hostname} Timeout")

    except Exception as e:

        failed += 1

        logging.error(
            f"{hostname} {e}"
        )

        print(f"{hostname} Error")

logging.info(
    f"Completed - Success:{success} Failed:{failed}"
)

print("\n========================")
print("Backup Finished")
print(f"Success : {success}")
print(f"Failed  : {failed}")
print("========================")