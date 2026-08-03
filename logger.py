import logging
from pathlib import Path
from typing import Optional


def setup_logger(log_file: Path | str | None = None, level: str = "INFO") -> logging.Logger:
    log_path = Path(log_file or Path(__file__).resolve().parent / "logs" / "backup.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("backup_app")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Netmiko reports connection failures through this application logger.
    # Suppress Paramiko's duplicate background-thread traceback for the same
    # failure, while retaining the clear device-specific error below.
    logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL)

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
