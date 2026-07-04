import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_FOLDER, LOG_LEVEL

# ==============================
# Create Log Directory
# ==============================

Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)

# ==============================
# Logger Formatter
# ==============================

LOG_FORMAT = (
    "[%(asctime)s] "
    "[%(levelname)s] "
    "[%(name)s] "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

formatter = logging.Formatter(
    LOG_FORMAT,
    DATE_FORMAT
)

# ==============================
# Main Logger
# ==============================

logger = logging.getLogger("AI_Dubbing")

logger.setLevel(getattr(logging, LOG_LEVEL))

if not logger.handlers:

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        os.path.join(LOG_FOLDER, "server.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# ==============================
# Helper Functions
# ==============================


def info(message: str):
    logger.info(message)


def warning(message: str):
    logger.warning(message)


def error(message: str):
    logger.error(message)


def debug(message: str):
    logger.debug(message)


def critical(message: str):
    logger.critical(message)


# ==============================
# Task Logger
# ==============================

def task_log(task_id: str, stage: str, message: str):

    logger.info(
        f"[Task={task_id}] "
        f"[Stage={stage}] "
        f"{message}"
    )


def task_error(task_id: str, stage: str, message: str):

    logger.error(
        f"[Task={task_id}] "
        f"[Stage={stage}] "
        f"{message}"
    )
