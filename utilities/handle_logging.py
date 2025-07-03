import os
from datetime import datetime
import logging
import sys

#class MultilineFormatter(logging.Formatter):
#    def format(self, record):
#        # Get the basic formatted record
#        header = f"{self.formatTime(record)} - {record.levelname}"
#        message = record.getMessage()  # This properly gets the formatted message
#        
#        if message:  # Only add newline if there's actually a message
#            return f"{header}\n{message}"
#        else:
#            return f"{header}\n[empty message]"  # Debug empty messages

def set_up_logging(dir_output):

    dir_logs = os.path.join(dir_output, 'logs')
    path_log = os.path.join(dir_logs,
                datetime.now().strftime("log_%Y-%m-%d_%H-%M-%S.txt"))

    ## Create custom formatter
    #formatter = MultilineFormatter('%(asctime)s - %(levelname)s')
    
    # File handler
    file_handler = logging.FileHandler(path_log)
    #file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    #console_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[file_handler, console_handler]
    )

    return
