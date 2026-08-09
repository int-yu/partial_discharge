from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import default_log_path

LOGGER_NAME = "pd_diagnosis"


def configure_logging(log_path: Path | None = None) -> Path:
    path = (log_path or default_log_path()).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    package_logger = logging.getLogger(LOGGER_NAME)
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = True
    for handler in list(package_logger.handlers):
        if getattr(handler, "_pd_diagnosis_managed", False):
            package_logger.removeHandler(handler)
            handler.close()

    file_handler = RotatingFileHandler(
        path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    setattr(file_handler, "_pd_diagnosis_managed", True)
    package_logger.addHandler(file_handler)
    return path
