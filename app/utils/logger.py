import datetime
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

FORMATTER = (
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
)


def get_logger(
    logger_name,
    log_level_console=logging.NOTSET,
    log_level_file=logging.NOTSET,
    script_action="",
):
    """
    Create a logger and add console and file logging handlers to it
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_get_console_handler(log_level=log_level_console))
    logger.addHandler(
        _get_file_handler(
            log_level=log_level_file,
            module_name=logger_name,
            script_action=script_action,
        )
    )
    logger.propagate = False
    return logger


def _get_console_handler(log_level):
    """
    Create and configure a console logging handler
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    console_handler.setLevel(log_level)
    return console_handler


def _get_file_handler(log_level, module_name, script_action):
    """
    Create and configure a file logging handler
    """
    log_dir = "../../log"
    Path(log_dir).mkdir(exist_ok=True)
    log_file = (
        f'{log_dir}/{datetime.datetime.now().strftime("%Y%m%d")}-{module_name}'
        f'{f"-{script_action}" if script_action else ""}.log'
    )

    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FORMATTER))
    file_handler.setLevel(log_level)
    return file_handler


class CustomFormatter(logging.Formatter):
    """
    Custom colorful logger
    """

    grey = "\x1b[38;20m"
    blue = "\x1b[33;94m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + FORMATTER + reset,
        logging.INFO: blue + FORMATTER + reset,
        logging.WARNING: yellow + FORMATTER + reset,
        logging.ERROR: red + FORMATTER + reset,
        logging.CRITICAL: bold_red + FORMATTER + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
