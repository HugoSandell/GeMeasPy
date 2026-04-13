"""Logger for test code"""

import logging
import os
from datetime import datetime

import gemeaspy

logger = logging.getLogger("gemeaspy_tests")
logger.setLevel(logging.DEBUG)
_initialized = False

debug = logger.debug
critical = logger.critical
info = logger.info
error = logger.error
warning = logger.warning

def initialize_logger():
    global _initialized
    if _initialized:
        return
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    log_dir = os.path.normpath(f"{os.path.dirname(gemeaspy.__file__)}/../log")
    log_file_path = f"{log_dir}/tests{now}.log"
    log_format = "%(asctime)s %(levelname)-6s [%(module)s:%(lineno)s] %(message)s"
    log_date_format = "%Y-%m-%d %H:%M:%S"
    
    general_formatter = logging.Formatter(log_format, log_date_format)
    os.makedirs(log_dir, exist_ok=True)
    tests_handler = logging.FileHandler(log_file_path)
    tests_handler.setFormatter(general_formatter)
    logger.addHandler(tests_handler)
    _initialized = True

initialize_logger()