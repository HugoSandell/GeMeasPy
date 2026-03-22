"""Logger for test code"""
import logging

logger = logging.Logger("gemeaspy_tests", logging.DEBUG)

debug = logger.debug
critical = logger.critical
info = logger.info
error = logger.error
warning = logger.warning

def initialise_logger():
    from os.path import dirname
    from datetime import datetime
    import gemeaspy
    
    now = "".join(filter(lambda c: str.isalnum(c), datetime.now().isoformat("-").split(".")[0]))
    log_file_path = f"{dirname(gemeaspy.__file__)}/../log/tests{now}.log" 
    log_format = "%(asctime)s %(levelname)-6s [%(module)s:%(lineno)s] %(message)s"
    log_date_format = "%Y-%m-%d %H:%M:%S"
    
    general_formatter = logging.Formatter(log_format, log_date_format)
    tests_handler = logging.FileHandler(log_file_path)
    tests_handler.setFormatter(general_formatter)
    logger.addHandler(tests_handler)

initialise_logger()