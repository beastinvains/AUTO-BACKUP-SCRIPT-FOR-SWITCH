import argparse
import time

from config import load_config
from logger import setup_logger


def _choose_mode() -> str:
    """Ask an interactive user whether to run now or keep scheduling."""
    print("\nInfrastructure configuration backup utility")
    print("1. Run a backup now, then exit")
    print("2. Keep running and execute the configured backup schedules")

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
    group.add_argument("--schedule", action="store_true", help="keep running and execute the stored backup schedules")
    args = parser.parse_args()
    if args.backup_now:
        return "now"
    if args.schedule:
        return "schedule"
    return None


def _seed_default_schedule(config, logger) -> None:
    """Carry the old config-file window into a schedule row, once.

    The legacy CLI hard-coded a single daily window from ``settings.backup_time``.  Phase 3
    stores schedules as rows, so on an empty schedule table that window is written once and
    is thereafter editable from the Schedules screen like any other.
    """
    from backend.app import schedule_service
    from schedule_service import ScheduleFrequency, ScheduleSpec

    if schedule_service.list():
        return
    frequency = ScheduleFrequency.DAILY if config.schedule == "daily" else ScheduleFrequency.HOURLY
    spec = ScheduleSpec(name="default", frequency=frequency, run_at=config.backup_time)
    schedule_service.create(spec, actor="cli")
    logger.info("Seeded schedule 'default' (%s at %s UTC) from configuration", frequency.value, config.backup_time)


def main() -> None:
    mode = _parse_mode() or _choose_mode()
    config = load_config()
    logger = setup_logger(config.log_file, config.log_level)

    # The legacy CLI is intentionally just a compatibility shell.  It does not
    # own SSH, versioning, or storage behavior; those live in Phase 2 services,
    # and scheduling is the same runner and service the API uses.
    from backend.app import run_scheduled_backup, schedule_runner
    from database.models import Base
    from database.session import engine

    Base.metadata.create_all(engine)
    logger.info("Backup application started")

    if mode == "now":
        logger.info("Starting backup requested by user")
        result = run_scheduled_backup()
        logger.info("Backup finished: %d successful, %d failed", result["success_count"], result["failure_count"])
        return

    _seed_default_schedule(config, logger)
    schedule_runner.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        schedule_runner.stop()


if __name__ == "__main__":
    main()
