import logging as _logging

logger = _logging.Logger("gemeaspy_tests", _logging.DEBUG)

debug = logger.debug
critical = logger.critical
info = logger.info
error = logger.error
warning = logger.warning

def configure_logs():
    from os.path import dirname
    import gemeaspy
    
    log_file_path = dirname(gemeaspy.__file__) + "/../log/gemeaspy_tests.log" 
    log_format = "%(asctime)s %(levelname)-6s [%(module)s:%(lineno)s] %(message)s"
    log_date_format = "%Y-%m-%d %H:%M:%S"
    
    general_formatter = _logging.Formatter(log_format, log_date_format)
    tests_handler = _logging.FileHandler(log_file_path)
    tests_handler.setFormatter(general_formatter)
    logger.addHandler(tests_handler)

configure_logs()