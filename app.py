import argparse
import time

from backup import backup_devices
from config import load_config
from credentials import load_environment
from devices import load_devices
from logger import setup_logger
from scheduler import BackupScheduler


def _choose_mode() -> str:
    """Ask an interactive user whether to run now or keep scheduling."""
    print("\nJuniper/Cisco backup utility")
    print("1. Run a backup now, then exit")
    print("2. Keep running and back up every day at 02:00")

    while True:
        choice = input("Choose 1 or 2: ").strip()
        if choice == "1":
            return "now"
        if choice == "2":
            return "schedule"
        print("Please enter 1 or 2.")


def _parse_mode() -> str | None:
    parser = argparse.ArgumentParser(description="Network device backup utility")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backup-now", action="store_true", help="run one backup immediately and exit")
    group.add_argument("--schedule", action="store_true", help="keep running and back up daily at 02:00")
    args = parser.parse_args()
    if args.backup_now:
        return "now"
    if args.schedule:
        return "schedule"
    return None


def main() -> None:
    mode = _parse_mode() or _choose_mode()
    config = load_config()
    load_environment(config.env_file)

    devices = load_devices(config.devices_file)
    logger = setup_logger(config.log_file, config.log_level)

    logger.info("Backup application started")
    logger.info("Loaded %d device(s)", len(devices))

    if mode == "now":
        logger.info("Starting backup requested by user")
        results = backup_devices(devices, config, logger)
        successful = sum(result["status"] == "success" for result in results)
        logger.info("Backup finished: %d/%d device(s) successful", successful, len(results))
        return

    def scheduled_backup() -> None:
        """Run scheduled work with the latest local settings."""
        current_config = load_config()
        current_devices = load_devices(current_config.devices_file)
        backup_devices(current_devices, current_config, logger)

    scheduler = BackupScheduler(callback=scheduled_backup, config=config, logger=logger)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
