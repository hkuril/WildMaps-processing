import os
from datetime import datetime
import logging
import sys

from logger_store import log as shared_log  # Just to reference the name
import logger_store  # For setting it

class CustomFormatter(logging.Formatter):
    def format(self, record):
        show_timestamp = getattr(record, 'show_timestamp', True)
        
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        message = record.getMessage()
        if not show_timestamp:
            return message

        if '\n' in message or len(message) > 80:
            return f"{timestamp}\n{message}"
        else:
            return f"{timestamp} {message}"

class ConsoleFilter(logging.Filter):
    def filter(self, record):
        return getattr(record, 'to_console', False)

class LoggerWrapper:
    def __init__(self, logfile='app.log'):
        self.logger = logging.getLogger(logfile)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        formatter = CustomFormatter()

        # File handler (logs everything)
        fh = logging.FileHandler(logfile, encoding='utf-8')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Console handler (conditional)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        ch.addFilter(ConsoleFilter())
        self.logger.addHandler(ch)

    def log(self, level, message, to_console=True, show_timestamp = True):
        self.logger.log(level, message, extra={'to_console': to_console,
                                               'show_timestamp' : show_timestamp})

    def debug(self, message, to_console=True, show_timestamp = True):
        self.log(logging.DEBUG, message, to_console, show_timestamp)

    def info(self, message, to_console=True, show_timestamp = True):
        self.log(logging.INFO, message, to_console, show_timestamp)

    def warning(self, message, to_console=True, show_timestamp = True):
        self.log(logging.WARNING, message, to_console, show_timestamp)

    def error(self, message, to_console=True, show_timestamp = True):
        self.log(logging.ERROR, message, to_console, show_timestamp)

    def critical(self, message, to_console=True, show_timestamp = True):
        self.log(logging.CRITICAL, message, to_console, show_timestamp)

def initialise_logging(dir_output):
    path_log = os.path.join(dir_output, datetime.now().strftime("log_%Y-%m-%d_%H-%M-%S.txt"))
    logger_store.log = LoggerWrapper(path_log)
    logger_store.log.info(f"Writing logs to {path_log}")

