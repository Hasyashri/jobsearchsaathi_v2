"""
logging_config.py — Console + rotating file logging setup.
Call configure_logging() once at startup.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_dir: str = "logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root.handlers
    )
    has_file = any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    if not has_console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root.addHandler(ch)

    if not has_file:
        fh = RotatingFileHandler(
            Path(log_dir) / "app.log",
            maxBytes=2_000_000,   # 2 MB
            backupCount=5,
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)
