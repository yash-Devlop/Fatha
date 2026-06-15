import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo


class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, ZoneInfo("Asia/Kolkata"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class AppLogger:
    def __init__(self, log_path: str = "C:\\Fatha\\logs\\logs.log"):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        self.logger = logging.getLogger(log_path)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            formatter = ISTFormatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def info(self, message: str):
        self.logger.info(message)

    def warn(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)
