import json
import logging
from time import perf_counter


def get_discovery_logger() -> logging.Logger:
    logger = logging.getLogger("phase1.discovery")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_discovery(logger: logging.Logger, **fields: object) -> None:
    safe = {key: value for key, value in fields.items()
            if not any(secret in key.lower() for secret in ("password", "secret", "credential", "private_key"))}
    logger.info(json.dumps(safe, default=str, sort_keys=True))

