"""
backend/app/utils/logging_config.py
======================================
Central logging setup (Section 40). Logs model loading, dataset loading,
embedding loading, recommendation requests, prediction time, and errors.
Never logs raw request bodies / user-identifying information — only the
non-sensitive query parameters relevant to debugging (pollutant/pH/T/S are
environmental parameters, not personal data, so they are safe to log at
INFO level for demo/debugging purposes).
"""
import logging
import sys

from enzaime_core import config as core_config


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("enzaime")
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers on reload)

    logger.setLevel(core_config.LOG_LEVEL)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
