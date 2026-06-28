"""Central logging configuration for ArtisanMarket."""

import logging
import os

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Noisy third-party loggers kept at WARNING so app logs stay readable at DEBUG
NOISY_LOGGERS: list[str] = ["pymongo", "neo4j", "urllib3", "sentence_transformers"]


def setup_logging(level: str | None = None) -> None:
    """Configure root logging. Call once from an application entry point.

    Args:
        level: Log level name; falls back to the LOG_LEVEL env var (default INFO)
    """
    logging.basicConfig(
        level=level or LOG_LEVEL,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
