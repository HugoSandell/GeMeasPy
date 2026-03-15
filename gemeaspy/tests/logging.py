import logging as _logging
from logging import debug, critical, info, error, warning 

def configure_logs():
    from os.path import dirname, join, abspath
    import gemeaspy
    log_file_path = dirname(gemeaspy.__file__) + "/../log/test_generation.log" 
    log_format = "%(asctime)s %(levelname)-6s [%(module)-12s:%(lineno)s] %(message)s"
    log_date_format = "%Y-%m-%d %H:%M:%S"
    _logging.basicConfig(
        level=_logging.DEBUG,
        filemode="a",
        filename=log_file_path, 
        format=log_format, 
        datefmt=log_date_format,
    )

configure_logs()