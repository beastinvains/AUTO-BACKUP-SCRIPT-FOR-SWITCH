import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import perf_counter
from typing import Iterable, List

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from config import AppConfig
from credentials import get_credentials
from devices import Device
from logger import setup_logger
from reports.health import parse_power_supplies_from_results
from reports.report_manager import ReportManager
from reports.report_models import CommandResult, DeviceReport
from utils import build_backup_path, ensure_directory, normalize_vendor


class BackupExecutionError(Exception):
    """Raised when a device backup cannot be completed."""


COMMANDS = {
    "juniper": [
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
    ],
    "cisco": [
        "show running-config",
        "show version",
        "show interfaces summary",
        "show vlan brief",
    ],
}


def backup_device(
    device: Device,
    config: AppConfig,
    logger=None,
    report_manager: ReportManager | None = None,
) -> dict:
    if logger is None:
        logger = setup_logger(config.log_file, config.log_level)

    today = datetime.now()
    backup_timestamp = today.strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = build_backup_path(config.backup_root, today, device.hostname)
    ensure_directory(backup_dir)
    device_report = DeviceReport(
        hostname=device.hostname,
        ip=device.ip,
        vendor=device.vendor,
        status="failed",
    )

    try:
        credentials = get_credentials(device.credential_profile, config.env_file)
        device_type = {
            "juniper": "juniper_junos",
            "cisco": "cisco_ios",
        }.get(normalize_vendor(device.vendor), "juniper_junos")
        logger.info("%s | connecting to %s", device.hostname, device.ip)
        connection = ConnectHandler(
            device_type=device_type,
            host=device.ip,
            port=device.port,
            username=credentials["username"],
            password=credentials["password"],
            timeout=config.timeout,
            banner_timeout=config.banner_timeout,
        )

        output_sections = []
        commands = COMMANDS.get(normalize_vendor(device.vendor), COMMANDS["juniper"])
        report_commands = (config.report_commands or {}).get(normalize_vendor(device.vendor), [])
        for index, command in enumerate(commands, start=1):
            started_at = perf_counter()
            try:
                output = connection.send_command(command, read_timeout=config.timeout)
                command_error = None
            except Exception as exc:
                output = f"Command Failed\n\n{exc}"
                command_error = str(exc)
            output_sections.append(
                f"===== Command {index}/{len(commands)}: {command} =====\n{output}\n"
            )

            if command in report_commands and report_manager:
                report_manager.add_command(
                    device_report,
                    CommandResult(
                        command=command,
                        status="failed" if command_error else "success",
                        execution_time=round(perf_counter() - started_at, 3),
                        output="" if command_error else output,
                        error=command_error,
                    ),
                )

        for command in report_commands:
            if command in commands:
                continue
            started_at = perf_counter()
            try:
                output = connection.send_command(command, read_timeout=config.timeout)
                result = CommandResult(
                    command=command,
                    status="success",
                    execution_time=round(perf_counter() - started_at, 3),
                    output=output,
                )
            except Exception as exc:
                result = CommandResult(
                    command=command,
                    status="failed",
                    execution_time=round(perf_counter() - started_at, 3),
                    error=str(exc),
                )
            if report_manager:
                report_manager.add_command(device_report, result)

        combined_output = "\n".join([
            f"===== {device.vendor.upper()} Backup =====",
            f"Device: {device.hostname}",
            f"IP Address: {device.ip}",
            f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}",
            f"=======================\n",
            *output_sections,
        ])

        file_path = backup_dir / f"backup_{backup_timestamp}.txt"
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(combined_output)

        connection.disconnect()
        device_report.status = "success"
        if report_manager:
            device_report.backup_file = report_manager.backup_file_reference(file_path)
            device_report.metadata["power_supplies"] = parse_power_supplies_from_results(
                [command.to_dict() for command in device_report.commands]
            )
            report_manager.add_device(device_report)
        logger.info("%s | backup completed", device.hostname)
        return {"hostname": device.hostname, "status": "success", "path": str(file_path)}
    except NetmikoAuthenticationException as exc:
        device_report.error = f"Authentication failed: {exc}"
        if report_manager:
            report_manager.add_device(device_report)
        logger.error("%s | authentication failed: %s", device.hostname, exc)
        raise BackupExecutionError(str(exc)) from exc
    except NetmikoTimeoutException as exc:
        device_report.error = f"Connection timeout: {exc}"
        if report_manager:
            report_manager.add_device(device_report)
        logger.error("%s | timeout while connecting: %s", device.hostname, exc)
        raise BackupExecutionError(str(exc)) from exc
    except Exception as exc:
        device_report.error = str(exc)
        if report_manager:
            report_manager.add_device(device_report)
        logger.error("%s | backup failed: %s", device.hostname, exc)
        raise BackupExecutionError(str(exc)) from exc


def backup_devices(devices: Iterable[Device], config: AppConfig, logger=None) -> List[dict]:
    device_list = list(devices)
    if logger is None:
        logger = setup_logger(config.log_file, config.log_level)
    try:
        report_manager: ReportManager | None = ReportManager(config.backup_root)
    except Exception as exc:
        # Reporting must never prevent a successful legacy backup.
        logger.error("Daily report initialization failed: %s", exc)
        report_manager = None
    if config.max_workers > 1 and len(device_list) > 1:
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = [
                executor.submit(backup_device, device, config, logger, report_manager)
                for device in device_list
            ]
            results: List[dict] = []
            for future in futures:
                try:
                    results.append(future.result())
                except BackupExecutionError as exc:
                    results.append({"hostname": exc.args[0].split("|", 1)[0].strip(), "status": "failed", "error": str(exc)})
        if report_manager:
            try:
                report_manager.save()
            except Exception as exc:
                logger.error("Daily report save failed: %s", exc)
        return results

    results: List[dict] = []
    for device in device_list:
        try:
            result = backup_device(device, config, logger, report_manager)
            results.append(result)
        except BackupExecutionError as exc:
            results.append({"hostname": device.hostname, "status": "failed", "error": str(exc)})
    if report_manager:
        try:
            report_manager.save()
        except Exception as exc:
            logger.error("Daily report save failed: %s", exc)
    return results
