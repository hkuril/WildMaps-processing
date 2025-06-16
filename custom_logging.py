import logging
import sys
from datetime import datetime

class CustomFormatter(logging.Formatter):
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        message = record.getMessage()
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

    def log(self, level, message, to_console=True):
        self.logger.log(level, message, extra={'to_console': to_console})

    def debug(self, message, to_console=True):
        self.log(logging.DEBUG, message, to_console)

    def info(self, message, to_console=True):
        self.log(logging.INFO, message, to_console)

    def warning(self, message, to_console=True):
        self.log(logging.WARNING, message, to_console)

    def error(self, message, to_console=True):
        self.log(logging.ERROR, message, to_console)

    def critical(self, message, to_console=True):
        self.log(logging.CRITICAL, message, to_console)
